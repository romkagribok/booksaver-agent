from __future__ import annotations

import threading
from datetime import UTC, datetime, timedelta

import pytest

from booksaver.application.remote_auth import (
    RemoteAuthBusy,
    RemoteAuthDenied,
    RemoteAuthenticationManager,
    RemoteBrowserResult,
    RemoteBrowserWork,
)
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
    ) -> RemoteBrowserResult:
        self.started.set()
        assert callable(on_ready)
        on_ready()
        while not self.release.wait(0.01):
            if work.cancel_event.is_set() or daemon_stop_event.is_set():
                return RemoteBrowserResult(RemoteAuthStatus.CANCELLED)
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
    runner = ControlledRunner(
        RemoteBrowserResult(RemoteAuthStatus.SUCCEEDED, cookies_json="[]")
    )
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
    runner = ControlledRunner(
        RemoteBrowserResult(RemoteAuthStatus.SUCCEEDED, cookies_json="[]")
    )
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


def test_manager_redacts_capture_failure_and_releases_browser_gate() -> None:
    runner = ControlledRunner(
        RemoteBrowserResult(RemoteAuthStatus.SUCCEEDED, cookies_json="[]")
    )
    messages: list[str] = []
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
    )
    launch = manager.create(123, 123)
    grant = manager.exchange(launch.url.rsplit("/", 1)[-1], 123)
    runner.release.set()
    for _ in range(100):
        if messages:
            break
        threading.Event().wait(0.01)

    assert messages == [
        "Booking.com connection failed and no session was saved. Send /connect to retry."
    ]
    assert manager.viewer_state(grant.session_token).status is RemoteAuthStatus.FAILED
    assert not gate.locked()


def test_terminal_viewer_capability_is_pruned_at_attempt_expiry() -> None:
    now = datetime(2026, 7, 20, tzinfo=UTC)
    current = [now]
    runner = ControlledRunner(
        RemoteBrowserResult(RemoteAuthStatus.SUCCEEDED, cookies_json="[]")
    )
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
