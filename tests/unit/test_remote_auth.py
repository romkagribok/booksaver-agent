from __future__ import annotations

import threading
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import cast

import pytest

from booksaver.application.remote_auth import (
    ATTEMPT_LIFETIME_CEILING,
    DETACH_GRACE,
    RemoteAuthBusy,
    RemoteAuthDenied,
    RemoteAuthenticationManager,
    RemoteBrowserResult,
    RemoteBrowserWork,
)
from booksaver.domain.dom_incident import IncidentDraft
from booksaver.domain.remote_auth import LoginDevice, RemoteAuthSettings, RemoteAuthStatus


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
        assert callable(on_ready)
        on_ready()
        self.started.set()
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
        assert callable(on_ready)
        on_ready()
        with self._condition:
            call_index = len(self.calls)
            self.calls.append(call)
            self._condition.notify_all()
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


def test_manager_binds_launch_to_user_reopens_for_owner_and_captures_once() -> None:
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
    token = launch.url.rsplit("/", 1)[-1]
    assert manager.expected_telegram_user(token) == 123
    with pytest.raises(RemoteAuthDenied):
        manager.exchange(token, 999)

    first = manager.exchange(token, 123)
    assert runner.started.wait(1)
    # The owner may reopen the link while the login is alive; the previous viewer
    # capability is revoked and other users are still denied.
    with pytest.raises(RemoteAuthDenied):
        manager.exchange(token, 999)
    grant = manager.exchange(token, 123)
    with pytest.raises(RemoteAuthDenied):
        manager.viewer_state(first.session_token)
    state = manager.viewer_state(grant.session_token)
    assert state.status is RemoteAuthStatus.CONNECTED
    assert state.websocket_path == "/websockify"
    assert state.websocket_token
    assert state.message == "Sign in with your Booking.com email and password."

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
            "Booking.com connected successfully. Your login is saved.",
        )
    ]
    assert manager.viewer_state(grant.session_token).status is RemoteAuthStatus.SUCCEEDED
    assert not gate.locked()


def test_connection_notice_precedes_immediate_inventory_completion() -> None:
    runner = ControlledRunner(RemoteBrowserResult(RemoteAuthStatus.SUCCEEDED, cookies_json="[]"))
    events: list[str] = []
    completed = threading.Event()
    gate = threading.Lock()

    def refresh(user_id: int) -> None:
        assert user_id == 123
        assert gate.acquire(blocking=False)
        try:
            events.append("inventory completed")
        finally:
            gate.release()
            completed.set()

    manager = RemoteAuthenticationManager(
        _settings(),
        runner,
        threading.Event(),
        lambda _user_id, _raw: events.append("session saved"),
        lambda _chat_id, text: events.append(text),
        on_success=refresh,
        browser_gate=gate,
    )
    launch = manager.create(123, 123)
    manager.exchange(launch.url.rsplit("/", 1)[-1], 123)
    runner.release.set()
    assert completed.wait(1)
    manager.stop_all()

    assert events == [
        "session saved",
        "Booking.com connected successfully. Your login is saved.",
        "inventory completed",
    ]
    assert not gate.locked()


def test_post_connect_callback_failure_preserves_session_and_redacts_error(
    caplog: pytest.LogCaptureFixture,
) -> None:
    runner = ControlledRunner(RemoteBrowserResult(RemoteAuthStatus.SUCCEEDED, cookies_json="[]"))
    messages: list[str] = []
    completed = threading.Event()
    gate = threading.Lock()

    def notify(_chat_id: int, text: str) -> None:
        messages.append(text)
        if "do not need to reconnect" in text:
            completed.set()

    def refresh(_user_id: int) -> None:
        raise RuntimeError("sensitive-session-material")

    manager = RemoteAuthenticationManager(
        _settings(),
        runner,
        threading.Event(),
        lambda _user_id, _raw: None,
        notify,
        on_success=refresh,
        browser_gate=gate,
    )
    launch = manager.create(123, 123)
    grant = manager.exchange(launch.url.rsplit("/", 1)[-1], 123)
    runner.release.set()
    assert completed.wait(1)
    manager.stop_all()

    assert manager.viewer_state(grant.session_token).status is RemoteAuthStatus.SUCCEEDED
    assert len(messages) == 2
    assert "connected successfully" in messages[0]
    assert "Send /bookings to retry" in messages[1]
    assert "RuntimeError" in caplog.text
    assert "sensitive-session-material" not in caplog.text + " ".join(messages)
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
        "Booking.com connected successfully. Your login is saved."
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
        "Booking.com connected successfully. Your login is saved."
    ]
    assert manager.viewer_state(grant.session_token).status is RemoteAuthStatus.SUCCEEDED

    current[0] = now + timedelta(seconds=152)
    with pytest.raises(RemoteAuthDenied):
        manager.viewer_state(grant.session_token)


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

    launch = manager.create(123, 123)
    manager.exchange(launch.url.rsplit("/", 1)[-1], 123)
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

    launch = manager.create(123, 123)
    manager.exchange(launch.url.rsplit("/", 1)[-1], 123)
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

    launch = manager.create(123, 123)
    manager.exchange(launch.url.rsplit("/", 1)[-1], 123)
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
    token = launch.url.rsplit("/", 1)[-1]
    grant = manager.exchange(token, 123)
    assert runner.started.wait(1)
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
    grant = manager.exchange(launch.url.rsplit("/", 1)[-1], 123)
    assert runner.started.wait(1)
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
    first_grant = manager.exchange(first.url.rsplit("/", 1)[-1], 123)
    runner.wait_for_call(0)

    replacement = manager.create(123, 123)

    assert replacement.url != first.url
    assert manager.viewer_state(first_grant.session_token).status is RemoteAuthStatus.CANCELLED
    assert not manager.cancel(first_grant.session_token)
    replacement_grant = manager.exchange(
        replacement.url.rsplit("/", 1)[-1],
        123,
    )
    runner.wait_for_call(1)
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
    launch = manager.create(123, 123)
    manager.exchange(launch.url.rsplit("/", 1)[-1], 123)
    first_call = runner.wait_for_call(0)
    replacements: list[str] = []

    thread = threading.Thread(target=lambda: replacements.append(manager.create(123, 123).url))
    thread.start()
    assert first_call.work.cancel_event.wait(1)

    assert not gate.acquire(blocking=False)
    first_call.release.set()
    thread.join(timeout=1)
    assert not thread.is_alive()
    assert len(replacements) == 1
    manager.exchange(replacements[0].rsplit("/", 1)[-1], 123)
    runner.wait_for_call(1)
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
    grant = manager.exchange(first.url.rsplit("/", 1)[-1], 123)
    first_call = runner.wait_for_call(0)
    assert manager.cancel(grant.session_token)
    replacements: list[str] = []
    thread = threading.Thread(target=lambda: replacements.append(manager.create(123, 123).url))
    thread.start()
    first_call.release.set()
    thread.join(timeout=1)

    assert len(replacements) == 1
    manager.exchange(replacements[0].rsplit("/", 1)[-1], 123)
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
    launch = manager.create(123, 123)
    manager.exchange(launch.url.rsplit("/", 1)[-1], 123)
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

    launch = manager.create(123, 123)
    manager.exchange(launch.url.rsplit("/", 1)[-1], 123)
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
    launch = manager.create(123, 123)
    manager.exchange(launch.url.rsplit("/", 1)[-1], 123)
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
    launch = manager.create(123, 123)
    manager.exchange(launch.url.rsplit("/", 1)[-1], 123)
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

    assert all(not thread.is_alive() for thread in threads)
    assert len(launches) == 2
    assert len(set(launches)) == 2
    valid_tokens = []
    for url in launches:
        token = url.rsplit("/", 1)[-1]
        try:
            manager.expected_telegram_user(token)
        except RemoteAuthDenied:
            continue
        valid_tokens.append(token)
    assert len(valid_tokens) == 1
    assert len(runner.calls) == 1
    manager.exchange(valid_tokens[0], 123)
    runner.wait_for_call(1)
    assert len(runner.calls) == 2
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

    launch = manager.create(123, 123)
    manager.exchange(launch.url.rsplit("/", 1)[-1], 123)
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
    launch = manager.create(123, 123)
    manager.exchange(launch.url.rsplit("/", 1)[-1], 123)
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


@pytest.mark.parametrize("ending", ["cancel", "expire", "shutdown", "daemon_stop"])
def test_unopened_attempt_never_launches_and_releases_lease(ending: str) -> None:
    now = datetime(2026, 9, 6, tzinfo=UTC)
    current = [now]
    runner = ControlledRunner(RemoteBrowserResult(RemoteAuthStatus.FAILED))
    gate = threading.Lock()
    daemon_stop = threading.Event()
    captured: list[str] = []
    manager = RemoteAuthenticationManager(
        _settings(session_timeout_seconds=120),
        runner,
        daemon_stop,
        lambda _user_id, raw: captured.append(raw),
        lambda _chat_id, _text: None,
        browser_gate=gate,
        clock=lambda: current[0],
    )
    launch = manager.create(123, 123)
    token = launch.url.rsplit("/", 1)[-1]
    assert gate.locked()
    assert not runner.started.wait(0.05)
    with pytest.raises(RemoteAuthBusy):
        manager.create(456, 456)

    if ending == "cancel":
        assert manager.cancel_for_telegram_user(123)
    elif ending == "expire":
        current[0] = now + timedelta(seconds=121)
    elif ending == "shutdown":
        manager.stop_all()
    else:
        daemon_stop.set()

    for _ in range(100):
        if not gate.locked():
            break
        threading.Event().wait(0.01)
    assert not gate.locked()
    assert not runner.started.is_set()
    assert captured == []
    with pytest.raises(RemoteAuthDenied):
        manager.exchange(token, 123, login_device=LoginDevice.DESKTOP)
    manager.stop_all()


def test_replacing_unopened_attempt_only_launches_authenticated_replacement() -> None:
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
    first = manager.create(123, 123)
    replacement = manager.create(123, 123)
    assert runner.calls == []
    assert gate.locked()
    with pytest.raises(RemoteAuthDenied):
        manager.exchange(first.url.rsplit("/", 1)[-1], 123, login_device=LoginDevice.DESKTOP)
    manager.exchange(replacement.url.rsplit("/", 1)[-1], 123)
    call = runner.wait_for_call(0)
    assert call.work.login_device is LoginDevice.MOBILE
    assert len(runner.calls) == 1
    manager.stop_all()
    assert not gate.locked()


def test_device_is_bound_only_by_owner_exchange_and_cannot_be_replayed() -> None:
    runner = SequentialRunner()
    manager = RemoteAuthenticationManager(
        _settings(),
        runner,
        threading.Event(),
        lambda _user_id, _raw: None,
        lambda _chat_id, _text: None,
    )
    launch = manager.create(123, 123)
    token = launch.url.rsplit("/", 1)[-1]
    with pytest.raises(RemoteAuthDenied):
        manager.exchange(token, 456, login_device=LoginDevice.MOBILE)
    assert runner.calls == []
    manager.exchange(token, 123, login_device=LoginDevice.DESKTOP)
    call = runner.wait_for_call(0)
    assert call.work.login_device is LoginDevice.DESKTOP
    # Reopening does not resize the already-running browser or start a second one.
    manager.exchange(token, 123, login_device=LoginDevice.MOBILE)
    assert call.work.login_device is LoginDevice.DESKTOP
    assert len(runner.calls) == 1
    with pytest.raises(RemoteAuthDenied):
        manager.exchange(token, 456, login_device=LoginDevice.MOBILE)
    manager.stop_all()


def _clocked_manager(runner: SequentialRunner, messages: list[str]) -> tuple[
    RemoteAuthenticationManager, list[datetime]
]:
    current = [datetime(2026, 9, 23, 12, 0, tzinfo=UTC)]
    manager = RemoteAuthenticationManager(
        _settings(),
        runner,
        threading.Event(),
        lambda _user_id, _raw: None,
        lambda _chat_id, text: messages.append(text),
        clock=lambda: current[0],
    )
    return manager, current


def test_detached_viewer_keeps_login_alive_within_grace_and_reattaches() -> None:
    runner = SequentialRunner()
    messages: list[str] = []
    manager, current = _clocked_manager(runner, messages)
    launch = manager.create(123, 123)
    grant = manager.exchange(launch.url.rsplit("/", 1)[-1], 123)
    call = runner.wait_for_call(0)
    assert manager.detach(grant.session_token)
    current[0] += DETACH_GRACE - timedelta(seconds=1)
    # Returning within the grace period resumes the same attempt and clears the timer.
    assert manager.viewer_state(grant.session_token).status is RemoteAuthStatus.CONNECTED
    current[0] += DETACH_GRACE - timedelta(seconds=1)
    assert manager.viewer_state(grant.session_token).status is RemoteAuthStatus.CONNECTED
    assert not call.work.cancel_event.is_set()
    assert messages == []
    manager.stop_all()


def test_first_exchange_negotiates_the_framebuffer_from_the_viewer_area() -> None:
    runner = SequentialRunner()
    messages: list[str] = []
    manager, _current = _clocked_manager(runner, messages)
    launch = manager.create(123, 123)
    token = launch.url.rsplit("/", 1)[-1]
    manager.exchange(token, 123, viewer_area={"width": 390, "height": 585})
    call = runner.wait_for_call(0)
    assert call.work.display_size == (480, 720)
    assert call.work.framebuffer == (480, 720)
    # Reopening from a differently sized viewer never resizes the running browser.
    manager.exchange(token, 123, viewer_area={"width": 1000, "height": 300})
    assert call.work.framebuffer == (480, 720)
    manager.stop_all()


def test_resume_is_bound_to_the_launch_link_and_live_attempt() -> None:
    runner = SequentialRunner()
    messages: list[str] = []
    manager, _current = _clocked_manager(runner, messages)
    launch = manager.create(123, 123)
    token = launch.url.rsplit("/", 1)[-1]
    grant = manager.exchange(token, 123)
    runner.wait_for_call(0)
    assert manager.detach(grant.session_token)
    assert manager.resume(grant.session_token, token)
    with pytest.raises(RemoteAuthDenied):
        manager.resume(grant.session_token, "some-other-launch")
    with pytest.raises(RemoteAuthDenied):
        manager.resume("unknown-viewer", token)
    # A cookie from a finished attempt can never resume a later launch.
    assert manager.cancel(grant.session_token)
    with pytest.raises(RemoteAuthDenied):
        manager.resume(grant.session_token, token)
    manager.stop_all()


def test_worker_deadline_reads_close_a_detached_login_without_api_calls() -> None:
    runner = SequentialRunner()
    messages: list[str] = []
    manager, current = _clocked_manager(runner, messages)
    launch = manager.create(123, 123)
    grant = manager.exchange(launch.url.rsplit("/", 1)[-1], 123)
    call = runner.wait_for_call(0)
    assert manager.detach(grant.session_token)
    current[0] += DETACH_GRACE
    # No viewer or gateway call happens; the browser worker's periodic deadline read is enough.
    assert not call.work.expired(current[0])
    assert call.work.cancel_event.is_set()
    call.release.set()
    for _ in range(100):
        if messages:
            break
        threading.Event().wait(0.01)
    assert messages and "stayed closed" in messages[0]
    manager.stop_all()


def test_detached_viewer_that_never_returns_is_closed_after_grace() -> None:
    runner = SequentialRunner()
    messages: list[str] = []
    manager, current = _clocked_manager(runner, messages)
    launch = manager.create(123, 123)
    token = launch.url.rsplit("/", 1)[-1]
    grant = manager.exchange(token, 123)
    call = runner.wait_for_call(0)
    assert manager.detach(grant.session_token)
    assert manager.detach(grant.session_token)  # idempotent, keeps the first timestamp
    current[0] += DETACH_GRACE
    state = manager.viewer_state(grant.session_token)
    assert state.status is RemoteAuthStatus.CANCELLED
    assert "stayed closed" in state.message
    assert call.work.cancel_event.is_set()
    call.release.set()
    for _ in range(100):
        if messages:
            break
        threading.Event().wait(0.01)
    assert messages == [
        "The Booking.com login window stayed closed for a few minutes, so the connection "
        "ended. Send /connect when you're ready to try again."
    ]
    with pytest.raises(RemoteAuthDenied):
        manager.exchange(token, 123)
    manager.stop_all()


def test_explicit_cancel_still_ends_a_detached_login_immediately() -> None:
    runner = SequentialRunner()
    messages: list[str] = []
    manager, _current = _clocked_manager(runner, messages)
    launch = manager.create(123, 123)
    grant = manager.exchange(launch.url.rsplit("/", 1)[-1], 123)
    call = runner.wait_for_call(0)
    assert manager.detach(grant.session_token)
    assert manager.cancel(grant.session_token)
    assert call.work.cancel_event.is_set()
    assert manager.viewer_state(grant.session_token).message == "This connection was cancelled."
    assert not manager.detach(grant.session_token)
    manager.stop_all()


def test_viewer_activity_slides_expiry_up_to_the_lifetime_ceiling() -> None:
    runner = SequentialRunner()
    messages: list[str] = []
    manager, current = _clocked_manager(runner, messages)
    created = current[0]
    launch = manager.create(123, 123)
    assert launch.expires_at == created + timedelta(seconds=600)
    grant = manager.exchange(launch.url.rsplit("/", 1)[-1], 123)
    call = runner.wait_for_call(0)
    # Ongoing activity keeps a full window ahead of the last poll.
    current[0] = created + timedelta(minutes=9)
    state = manager.viewer_state(grant.session_token)
    assert state.status is RemoteAuthStatus.CONNECTED
    assert state.expires_at == created + timedelta(minutes=19)
    assert not call.work.expired(created + timedelta(minutes=15))
    current[0] = created + timedelta(minutes=18)
    assert manager.viewer_state(grant.session_token).expires_at == created + timedelta(minutes=28)
    # The ceiling from creation still bounds the login.
    current[0] = created + timedelta(minutes=27)
    state = manager.viewer_state(grant.session_token)
    assert state.expires_at == created + ATTEMPT_LIFETIME_CEILING
    current[0] = created + ATTEMPT_LIFETIME_CEILING
    assert manager.viewer_state(grant.session_token).status is RemoteAuthStatus.EXPIRED
    assert call.work.expired(current[0])
    manager.stop_all()
