from __future__ import annotations

import threading
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import cast

import pytest

from booksaver.application.remote_auth import (
    RemoteAuthBusy,
    RemoteAuthDenied,
    RemoteAuthenticationManager,
    RemoteBrowserResult,
    RemoteBrowserWork,
)
from booksaver.domain.dom_incident import IncidentDraft
from booksaver.domain.remote_auth import RemoteAuthSettings, RemoteAuthStatus


class ControlledRunner:
    def __init__(self, result: RemoteBrowserResult) -> None:
        self.result = result
        self.started = threading.Event()
        self.release = threading.Event()

    def run(
        self,
        work: RemoteBrowserWork,
        daemon_stop_event: threading.Event,
        on_ready: object,
        on_finalizing: object,
    ) -> RemoteBrowserResult:
        self.started.set()
        assert callable(on_ready)
        on_ready()
        while not self.release.wait(0.01):
            if work.cancel_event.is_set() or daemon_stop_event.is_set():
                return RemoteBrowserResult(RemoteAuthStatus.CANCELLED)
        if self.result.status is RemoteAuthStatus.SUCCEEDED:
            assert callable(on_finalizing)
            if not on_finalizing():
                return RemoteBrowserResult(RemoteAuthStatus.CANCELLED)
        return self.result


@dataclass
class RunnerCall:
    work: RemoteBrowserWork
    release: threading.Event = field(default_factory=threading.Event)


class SequentialRunner:
    def __init__(self, *, ignore_cancel_calls: set[int] | None = None) -> None:
        self.ignore_cancel_calls = ignore_cancel_calls or set()
        self.calls: list[RunnerCall] = []
        self._condition = threading.Condition()

    def run(
        self,
        work: RemoteBrowserWork,
        daemon_stop_event: threading.Event,
        on_ready: object,
        on_finalizing: object,
    ) -> RemoteBrowserResult:
        call = RunnerCall(work)
        with self._condition:
            call_index = len(self.calls)
            self.calls.append(call)
            self._condition.notify_all()
        assert callable(on_ready)
        on_ready()
        while not call.release.wait(0.005):
            if daemon_stop_event.is_set():
                return RemoteBrowserResult(RemoteAuthStatus.CANCELLED)
            if work.cancel_event.is_set() and call_index not in self.ignore_cancel_calls:
                return RemoteBrowserResult(RemoteAuthStatus.CANCELLED)
        if work.cancel_event.is_set():
            return RemoteBrowserResult(RemoteAuthStatus.CANCELLED)
        return RemoteBrowserResult(RemoteAuthStatus.FAILED)

    def wait_for_call(self, index: int) -> RunnerCall:
        with self._condition:
            assert self._condition.wait_for(lambda: len(self.calls) > index, timeout=1)
            return self.calls[index]


class FinalizingRunner:
    def __init__(self, result: RemoteBrowserResult) -> None:
        self.result = result
        self.finalizing = threading.Event()
        self.release = threading.Event()

    def run(
        self,
        work: RemoteBrowserWork,
        daemon_stop_event: threading.Event,
        on_ready: object,
        on_finalizing: object,
    ) -> RemoteBrowserResult:
        assert callable(on_ready)
        assert callable(on_finalizing)
        on_ready()
        if not on_finalizing():
            return RemoteBrowserResult(RemoteAuthStatus.CANCELLED)
        self.finalizing.set()
        assert self.release.wait(1)
        if work.cancel_event.is_set() or daemon_stop_event.is_set():
            return RemoteBrowserResult(RemoteAuthStatus.CANCELLED)
        return self.result


class DelayedFailureRunner:
    """Return a prepared failure even when lifecycle cancellation already won."""

    def __init__(self, draft: IncidentDraft) -> None:
        self.result = RemoteBrowserResult(
            RemoteAuthStatus.FAILED,
            incident_draft=draft,
        )
        self.started = threading.Event()
        self.release = threading.Event()

    def run(
        self,
        work: RemoteBrowserWork,
        daemon_stop_event: threading.Event,
        on_ready: object,
        on_finalizing: object,
    ) -> RemoteBrowserResult:
        del work, daemon_stop_event, on_finalizing
        assert callable(on_ready)
        on_ready()
        self.started.set()
        assert self.release.wait(1)
        return self.result


def _settings(**overrides: object) -> RemoteAuthSettings:
    values: dict[str, object] = {
        "enabled": True,
        "public_url": "https://connect.example.test",
        "session_timeout_seconds": 600,
    }
    values.update(overrides)
    return RemoteAuthSettings(**values)  # type: ignore[arg-type]


def test_remote_auth_settings_require_safe_https_origin() -> None:
    with pytest.raises(ValueError, match="HTTPS origin"):
        _settings(public_url="http://connect.example.test")
    with pytest.raises(ValueError, match="without credentials"):
        _settings(public_url="https://user:pass@example.test/path?secret=x")
    with pytest.raises(ValueError, match="HTTPS origin"):
        _settings(public_url="https://connect.example.test/path")
    with pytest.raises(ValueError, match="must differ"):
        _settings(listen_port=8080, websocket_port=8080)


def test_manager_binds_single_use_launch_to_user_and_captures_once() -> None:
    runner = ControlledRunner(RemoteBrowserResult(RemoteAuthStatus.SUCCEEDED, cookies_json="[]"))
    captured: list[tuple[int, str]] = []
    messages: list[tuple[int, str]] = []
    gate = threading.Lock()
    manager = RemoteAuthenticationManager(
        _settings(),
        runner,
        threading.Event(),
        lambda user_id, raw: captured.append((user_id, raw)),
        lambda chat_id, text: messages.append((chat_id, text)),
        browser_gate=gate,
    )

    launch = manager.create(123, 123)
    assert runner.started.wait(1)
    token = launch.url.rsplit("/", 1)[-1]
    assert manager.expected_telegram_user(token) == 123
    with pytest.raises(RemoteAuthDenied):
        manager.exchange(token, 999)

    grant = manager.exchange(token, 123)
    with pytest.raises(RemoteAuthDenied):
        manager.exchange(token, 123)
    state = manager.viewer_state(grant.session_token)
    assert state.status is RemoteAuthStatus.CONNECTED
    assert state.websocket_path == "/websockify"
    assert state.websocket_token
    assert "Booking.com email and password" in state.message
    assert "Google, Apple, and other external providers are disabled" in state.message

    with pytest.raises(RemoteAuthBusy):
        manager.create(456, 456)
    runner.release.set()
    assert runner.release.wait(1)
    assert runner.started.is_set()
    for _ in range(100):
        if captured:
            break
        threading.Event().wait(0.01)
    assert captured == [(123, "[]")]
    assert messages == [
        (
            123,
            "Booking.com connected successfully. Future checks will use your "
            "authenticated mobile-web prices.",
        )
    ]
    assert manager.viewer_state(grant.session_token).status is RemoteAuthStatus.SUCCEEDED
    assert not gate.locked()


def test_verified_attempt_is_finalizing_and_refuses_viewer_cancel() -> None:
    draft = cast(IncidentDraft, object())
    runner = FinalizingRunner(
        RemoteBrowserResult(
            RemoteAuthStatus.SUCCEEDED,
            cookies_json="[]",
            incident_draft=draft,
        )
    )
    sequence: list[str] = []
    messages: list[str] = []
    manager = RemoteAuthenticationManager(
        _settings(),
        runner,
        threading.Event(),
        lambda _user_id, _raw: sequence.append("capture"),
        lambda _chat_id, text: messages.append(text),
        incident_sink=lambda value: sequence.append(
            "incident" if value is draft else "wrong-incident"
        ),
    )

    launch = manager.create(123, 123)
    grant = manager.exchange(launch.url.rsplit("/", 1)[-1], 123)
    assert runner.finalizing.wait(1)

    state = manager.viewer_state(grant.session_token)
    assert state.status is RemoteAuthStatus.FINALIZING
    assert state.websocket_path is None
    assert state.websocket_token is None
    assert "verified; saving" in (state.message or "")
    assert not manager.cancel(grant.session_token)
    with pytest.raises(RemoteAuthBusy, match="being saved"):
        manager.create(123, 123)

    runner.release.set()
    for _ in range(100):
        if messages:
            break
        threading.Event().wait(0.01)

    assert sequence == ["capture", "incident"]
    assert manager.viewer_state(grant.session_token).status is RemoteAuthStatus.SUCCEEDED
    assert messages == [
        "Booking.com connected successfully. Future checks will use your "
        "authenticated mobile-web prices."
    ]


def test_finalizing_survives_ordinary_expiry_until_capture_commits() -> None:
    now = datetime(2026, 7, 20, tzinfo=UTC)
    current = [now]
    draft = cast(IncidentDraft, object())
    runner = FinalizingRunner(
        RemoteBrowserResult(
            RemoteAuthStatus.SUCCEEDED,
            cookies_json="[]",
            incident_draft=draft,
        )
    )
    sequence: list[str] = []
    messages: list[str] = []
    manager = RemoteAuthenticationManager(
        _settings(session_timeout_seconds=120),
        runner,
        threading.Event(),
        lambda _user_id, _raw: sequence.append("capture"),
        lambda _chat_id, text: messages.append(text),
        clock=lambda: current[0],
        incident_sink=lambda value: sequence.append(
            "incident" if value is draft else "wrong-incident"
        ),
    )

    launch = manager.create(123, 123)
    grant = manager.exchange(launch.url.rsplit("/", 1)[-1], 123)
    assert runner.finalizing.wait(1)

    current[0] = now + timedelta(seconds=121)
    assert manager.viewer_state(grant.session_token).status is RemoteAuthStatus.FINALIZING

    runner.release.set()
    for _ in range(100):
        if messages:
            break
        threading.Event().wait(0.01)

    assert sequence == ["capture", "incident"]
    assert messages == [
        "Booking.com connected successfully. Future checks will use your "
        "authenticated mobile-web prices."
    ]


def test_administrative_cancel_still_wins_during_finalizing() -> None:
    runner = FinalizingRunner(RemoteBrowserResult(RemoteAuthStatus.SUCCEEDED, cookies_json="[]"))
    captured: list[str] = []
    manager = RemoteAuthenticationManager(
        _settings(),
        runner,
        threading.Event(),
        lambda _user_id, raw: captured.append(raw),
        lambda _chat_id, _text: None,
    )

    manager.create(123, 123)
    assert runner.finalizing.wait(1)
    assert manager.cancel_for_telegram_user(123)
    runner.release.set()
    manager.stop_all()

    assert captured == []


def test_failure_incident_records_when_viewer_cancel_wins_before_worker_return() -> None:
    draft = cast(IncidentDraft, object())
    runner = DelayedFailureRunner(draft)
    incidents: list[IncidentDraft] = []
    manager = RemoteAuthenticationManager(
        _settings(),
        runner,
        threading.Event(),
        lambda _user_id, _raw: None,
        lambda _chat_id, _text: None,
        incident_sink=incidents.append,
    )

    launch = manager.create(123, 123)
    grant = manager.exchange(launch.url.rsplit("/", 1)[-1], 123)
    assert runner.started.wait(1)
    assert manager.cancel(grant.session_token)
    runner.release.set()
    for _ in range(100):
        if incidents:
            break
        threading.Event().wait(0.01)

    assert manager.viewer_state(grant.session_token).status is RemoteAuthStatus.CANCELLED
    assert incidents == [draft]
    manager.stop_all()


def test_failure_incident_records_when_expiry_wins_before_worker_return() -> None:
    now = datetime(2026, 7, 20, tzinfo=UTC)
    current = [now]
    draft = cast(IncidentDraft, object())
    runner = DelayedFailureRunner(draft)
    incidents: list[IncidentDraft] = []
    manager = RemoteAuthenticationManager(
        _settings(session_timeout_seconds=120),
        runner,
        threading.Event(),
        lambda _user_id, _raw: None,
        lambda _chat_id, _text: None,
        clock=lambda: current[0],
        incident_sink=incidents.append,
    )

    launch = manager.create(123, 123)
    grant = manager.exchange(launch.url.rsplit("/", 1)[-1], 123)
    assert runner.started.wait(1)
    current[0] = now + timedelta(seconds=121)
    assert manager.viewer_state(grant.session_token).status is RemoteAuthStatus.EXPIRED
    runner.release.set()
    for _ in range(100):
        if incidents:
            break
        threading.Event().wait(0.01)

    assert incidents == [draft]
    manager.stop_all()


def test_privacy_erasure_suppresses_late_failure_incident() -> None:
    draft = cast(IncidentDraft, object())
    runner = DelayedFailureRunner(draft)
    incidents: list[IncidentDraft] = []
    manager = RemoteAuthenticationManager(
        _settings(),
        runner,
        threading.Event(),
        lambda _user_id, _raw: None,
        lambda _chat_id, _text: None,
        incident_sink=incidents.append,
    )

    manager.create(123, 123)
    assert runner.started.wait(1)
    assert manager.cancel_for_telegram_user(123)
    runner.release.set()
    manager.stop_all()

    assert incidents == []


def test_shutdown_suppresses_late_failure_incident() -> None:
    draft = cast(IncidentDraft, object())
    runner = DelayedFailureRunner(draft)
    incidents: list[IncidentDraft] = []
    manager = RemoteAuthenticationManager(
        _settings(),
        runner,
        threading.Event(),
        lambda _user_id, _raw: None,
        lambda _chat_id, _text: None,
        incident_sink=incidents.append,
    )

    manager.create(123, 123)
    assert runner.started.wait(1)
    manager.stop_all(join_timeout=0)
    runner.release.set()
    manager.stop_all()

    assert incidents == []


def test_incident_failure_does_not_undo_committed_session(
    caplog: pytest.LogCaptureFixture,
) -> None:
    draft = cast(IncidentDraft, object())
    runner = ControlledRunner(
        RemoteBrowserResult(
            RemoteAuthStatus.SUCCEEDED,
            cookies_json="[]",
            incident_draft=draft,
        )
    )
    captured: list[str] = []
    messages: list[str] = []

    def _reject_incident(_draft: IncidentDraft) -> None:
        raise RuntimeError("sensitive incident detail")

    manager = RemoteAuthenticationManager(
        _settings(),
        runner,
        threading.Event(),
        lambda _user_id, raw: captured.append(raw),
        lambda _chat_id, text: messages.append(text),
        incident_sink=_reject_incident,
    )
    launch = manager.create(123, 123)
    grant = manager.exchange(launch.url.rsplit("/", 1)[-1], 123)
    runner.release.set()
    for _ in range(100):
        if messages:
            break
        threading.Event().wait(0.01)

    assert captured == ["[]"]
    assert manager.viewer_state(grant.session_token).status is RemoteAuthStatus.SUCCEEDED
    assert len(messages) == 1
    assert "incident recording failed" in caplog.text
    assert "sensitive incident detail" not in caplog.text


def test_success_without_finalization_latch_is_rejected() -> None:
    class InvalidRunner:
        def run(
            self,
            work: RemoteBrowserWork,
            daemon_stop_event: threading.Event,
            on_ready: object,
            on_finalizing: object,
        ) -> RemoteBrowserResult:
            del work, daemon_stop_event, on_finalizing
            assert callable(on_ready)
            on_ready()
            return RemoteBrowserResult(RemoteAuthStatus.SUCCEEDED, cookies_json="[]")

    captured: list[str] = []
    messages: list[str] = []
    manager = RemoteAuthenticationManager(
        _settings(),
        InvalidRunner(),
        threading.Event(),
        lambda _user_id, raw: captured.append(raw),
        lambda _chat_id, text: messages.append(text),
    )
    launch = manager.create(123, 123)
    grant = manager.exchange(launch.url.rsplit("/", 1)[-1], 123)
    for _ in range(100):
        if messages:
            break
        threading.Event().wait(0.01)

    assert captured == []
    assert manager.viewer_state(grant.session_token).status is RemoteAuthStatus.FAILED
    assert len(messages) == 1


def test_manager_preserves_expired_state_until_worker_teardown() -> None:
    now = datetime(2026, 7, 20, tzinfo=UTC)
    current = [now]
    runner = ControlledRunner(RemoteBrowserResult(RemoteAuthStatus.CANCELLED))
    messages: list[str] = []
    manager = RemoteAuthenticationManager(
        _settings(session_timeout_seconds=120),
        runner,
        threading.Event(),
        lambda _user_id, _raw: None,
        lambda _chat_id, text: messages.append(text),
        clock=lambda: current[0],
    )
    launch = manager.create(123, 123)
    assert runner.started.wait(1)
    token = launch.url.rsplit("/", 1)[-1]
    grant = manager.exchange(token, 123)
    current[0] = now + timedelta(seconds=121)
    state = manager.viewer_state(grant.session_token)
    assert state.status is RemoteAuthStatus.EXPIRED
    for _ in range(100):
        if messages:
            break
        threading.Event().wait(0.01)
    assert messages == [
        "Booking.com connection timed out. Send /connect when you're ready to try again."
    ]


def test_manager_cancellation_is_idempotent_and_never_captures() -> None:
    runner = ControlledRunner(RemoteBrowserResult(RemoteAuthStatus.SUCCEEDED, cookies_json="[]"))
    captured: list[str] = []
    manager = RemoteAuthenticationManager(
        _settings(),
        runner,
        threading.Event(),
        lambda _user_id, raw: captured.append(raw),
        lambda _chat_id, _text: None,
    )
    launch = manager.create(123, 123)
    assert runner.started.wait(1)
    grant = manager.exchange(launch.url.rsplit("/", 1)[-1], 123)
    assert manager.cancel(grant.session_token)
    assert not manager.cancel(grant.session_token)
    runner.release.set()
    manager.stop_all()
    assert captured == []


def test_same_user_connect_immediately_replaces_active_attempt() -> None:
    runner = SequentialRunner()
    messages: list[str] = []
    gate = threading.Lock()
    manager = RemoteAuthenticationManager(
        _settings(),
        runner,
        threading.Event(),
        lambda _user_id, _raw: None,
        lambda _chat_id, text: messages.append(text),
        browser_gate=gate,
    )
    first = manager.create(123, 123)
    runner.wait_for_call(0)
    first_grant = manager.exchange(first.url.rsplit("/", 1)[-1], 123)

    replacement = manager.create(123, 123)
    runner.wait_for_call(1)

    assert replacement.url != first.url
    assert manager.viewer_state(first_grant.session_token).status is RemoteAuthStatus.CANCELLED
    assert not manager.cancel(first_grant.session_token)
    replacement_grant = manager.exchange(
        replacement.url.rsplit("/", 1)[-1],
        123,
    )
    assert (
        manager.viewer_state(replacement_grant.session_token).status is RemoteAuthStatus.CONNECTED
    )
    assert messages == []
    assert gate.locked()
    manager.stop_all()
    assert not gate.locked()


def test_same_user_replacement_reserves_gate_during_worker_teardown() -> None:
    runner = SequentialRunner(ignore_cancel_calls={0})
    gate = threading.Lock()
    manager = RemoteAuthenticationManager(
        _settings(),
        runner,
        threading.Event(),
        lambda _user_id, _raw: None,
        lambda _chat_id, _text: None,
        browser_gate=gate,
        replacement_join_timeout=1.0,
    )
    manager.create(123, 123)
    first_call = runner.wait_for_call(0)
    replacements: list[str] = []

    thread = threading.Thread(target=lambda: replacements.append(manager.create(123, 123).url))
    thread.start()
    assert first_call.work.cancel_event.wait(1)

    assert not gate.acquire(blocking=False)
    first_call.release.set()
    thread.join(timeout=1)
    assert not thread.is_alive()
    runner.wait_for_call(1)
    assert len(replacements) == 1
    assert gate.locked()
    manager.stop_all()


def test_same_user_connect_replaces_pagehide_cancelled_worker() -> None:
    runner = SequentialRunner(ignore_cancel_calls={0})
    messages: list[str] = []
    manager = RemoteAuthenticationManager(
        _settings(),
        runner,
        threading.Event(),
        lambda _user_id, _raw: None,
        lambda _chat_id, text: messages.append(text),
        replacement_join_timeout=1.0,
    )
    first = manager.create(123, 123)
    first_call = runner.wait_for_call(0)
    grant = manager.exchange(first.url.rsplit("/", 1)[-1], 123)
    assert manager.cancel(grant.session_token)
    replacements: list[str] = []
    thread = threading.Thread(target=lambda: replacements.append(manager.create(123, 123).url))
    thread.start()
    first_call.release.set()
    thread.join(timeout=1)

    assert len(replacements) == 1
    runner.wait_for_call(1)
    assert messages == []
    manager.stop_all()


def test_same_user_replacement_timeout_never_starts_second_browser() -> None:
    runner = SequentialRunner(ignore_cancel_calls={0})
    gate = threading.Lock()
    manager = RemoteAuthenticationManager(
        _settings(),
        runner,
        threading.Event(),
        lambda _user_id, _raw: None,
        lambda _chat_id, _text: None,
        browser_gate=gate,
        replacement_join_timeout=0.01,
    )
    manager.create(123, 123)
    first_call = runner.wait_for_call(0)

    with pytest.raises(RemoteAuthBusy, match="still closing"):
        manager.create(123, 123)
    assert len(runner.calls) == 1
    assert gate.locked()

    first_call.release.set()
    for _ in range(100):
        if not gate.locked():
            break
        threading.Event().wait(0.01)
    assert not gate.locked()

    manager.create(123, 123)
    runner.wait_for_call(1)
    manager.stop_all()


def test_different_user_cannot_reclaim_active_attempt() -> None:
    runner = SequentialRunner()
    manager = RemoteAuthenticationManager(
        _settings(),
        runner,
        threading.Event(),
        lambda _user_id, _raw: None,
        lambda _chat_id, _text: None,
    )
    manager.create(123, 123)
    first_call = runner.wait_for_call(0)

    with pytest.raises(RemoteAuthBusy, match="Another Booking.com login"):
        manager.create(456, 456)

    assert not first_call.work.cancel_event.is_set()
    assert len(runner.calls) == 1
    manager.stop_all()


def test_two_racing_same_user_connects_leave_one_browser_active() -> None:
    runner = SequentialRunner()
    gate = threading.Lock()
    manager = RemoteAuthenticationManager(
        _settings(),
        runner,
        threading.Event(),
        lambda _user_id, _raw: None,
        lambda _chat_id, _text: None,
        browser_gate=gate,
    )
    manager.create(123, 123)
    runner.wait_for_call(0)
    barrier = threading.Barrier(3)
    launches: list[str] = []

    def _replace() -> None:
        barrier.wait()
        launches.append(manager.create(123, 123).url)

    threads = [threading.Thread(target=_replace) for _ in range(2)]
    for thread in threads:
        thread.start()
    barrier.wait()
    for thread in threads:
        thread.join(timeout=2)

    runner.wait_for_call(2)
    assert all(not thread.is_alive() for thread in threads)
    assert len(launches) == 2
    assert len(set(launches)) == 2
    assert len(runner.calls) == 3
    assert gate.locked()
    manager.stop_all()


def test_manager_target_cancellation_is_scoped_and_prevents_capture() -> None:
    runner = ControlledRunner(RemoteBrowserResult(RemoteAuthStatus.SUCCEEDED, cookies_json="[]"))
    captured: list[tuple[int, str]] = []
    manager = RemoteAuthenticationManager(
        _settings(),
        runner,
        threading.Event(),
        lambda user_id, raw: captured.append((user_id, raw)),
        lambda _chat_id, _text: None,
    )

    manager.create(123, 123)
    assert runner.started.wait(1)

    assert not manager.cancel_for_telegram_user(456)
    assert manager.cancel_for_telegram_user(123)
    assert not manager.cancel_for_telegram_user(123)
    runner.release.set()
    manager.stop_all()

    assert captured == []


def test_manager_target_cancellation_waits_for_completed_capture() -> None:
    runner = ControlledRunner(RemoteBrowserResult(RemoteAuthStatus.SUCCEEDED, cookies_json="[]"))
    capture_started = threading.Event()
    release_capture = threading.Event()
    captured: list[tuple[int, str]] = []

    def _capture(user_id: int, raw: str) -> None:
        capture_started.set()
        assert release_capture.wait(1)
        captured.append((user_id, raw))

    manager = RemoteAuthenticationManager(
        _settings(),
        runner,
        threading.Event(),
        _capture,
        lambda _chat_id, _text: None,
    )
    manager.create(123, 123)
    assert runner.started.wait(1)
    runner.release.set()
    assert capture_started.wait(1)

    cancellation_result: list[bool] = []
    cancellation_finished = threading.Event()

    def _cancel() -> None:
        cancellation_result.append(manager.cancel_for_telegram_user(123))
        cancellation_finished.set()

    cancellation_thread = threading.Thread(target=_cancel)
    cancellation_thread.start()
    assert not cancellation_finished.wait(0.05)
    release_capture.set()
    cancellation_thread.join(timeout=1)

    assert cancellation_result == [False]
    assert captured == [(123, "[]")]


def test_manager_redacts_capture_failure_and_drops_recovered_incident(
    caplog: pytest.LogCaptureFixture,
) -> None:
    draft = cast(IncidentDraft, object())
    runner = ControlledRunner(
        RemoteBrowserResult(
            RemoteAuthStatus.SUCCEEDED,
            cookies_json="[]",
            incident_draft=draft,
        )
    )
    messages: list[str] = []
    incidents: list[IncidentDraft] = []
    gate = threading.Lock()

    def _reject(_user_id: int, _raw: str) -> None:
        raise ValueError("sensitive parser detail")

    manager = RemoteAuthenticationManager(
        _settings(),
        runner,
        threading.Event(),
        _reject,
        lambda _chat_id, text: messages.append(text),
        browser_gate=gate,
        incident_sink=incidents.append,
    )
    launch = manager.create(123, 123)
    grant = manager.exchange(launch.url.rsplit("/", 1)[-1], 123)
    runner.release.set()
    for _ in range(100):
        if messages:
            break
        threading.Event().wait(0.01)

    assert messages == [
        "Booking.com authentication was verified, but BookSaver could not save the "
        "session. No session was replaced. Send /connect to retry."
    ]
    state = manager.viewer_state(grant.session_token)
    assert state.status is RemoteAuthStatus.FAILED
    assert "could not save the session" in (state.message or "")
    assert incidents == []
    assert "ValueError" in caplog.text
    assert "sensitive parser detail" not in caplog.text
    assert not gate.locked()


def test_terminal_viewer_capability_is_pruned_at_attempt_expiry() -> None:
    now = datetime(2026, 7, 20, tzinfo=UTC)
    current = [now]
    runner = ControlledRunner(RemoteBrowserResult(RemoteAuthStatus.SUCCEEDED, cookies_json="[]"))
    messages: list[str] = []
    manager = RemoteAuthenticationManager(
        _settings(session_timeout_seconds=120),
        runner,
        threading.Event(),
        lambda _user_id, _raw: None,
        lambda _chat_id, text: messages.append(text),
        clock=lambda: current[0],
    )
    launch = manager.create(123, 123)
    grant = manager.exchange(launch.url.rsplit("/", 1)[-1], 123)
    runner.release.set()
    for _ in range(100):
        if messages:
            break
        threading.Event().wait(0.01)
    assert manager.viewer_state(grant.session_token).status is RemoteAuthStatus.SUCCEEDED

    current[0] = now + timedelta(seconds=121)
    with pytest.raises(RemoteAuthDenied):
        manager.viewer_state(grant.session_token)
