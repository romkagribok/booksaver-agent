from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from booksaver.domain.remote_auth import (
    LoginDevice,
    RemoteAuthSettings,
    RemoteAuthStatus,
    TelegramMiniAppIdentity,
    ViewerGrant,
    ViewerState,
)
from booksaver.infrastructure.remote_auth.gateway import RemoteAuthHttpApp


class StubManager:
    def __init__(self) -> None:
        self.launch_token = "launch-secret"
        self.viewer_token = "viewer-secret"
        self.user_id = 123
        self.cancelled: list[str] = []
        self.detached: list[str] = []
        self.exchanges: list[tuple[str, int, LoginDevice]] = []

    def expected_telegram_user(self, token: str) -> int:
        if token != self.launch_token:
            raise ValueError("bad launch")
        return self.user_id

    def exchange(
        self, token: str, user_id: int, *, login_device: LoginDevice = LoginDevice.MOBILE,
    ) -> ViewerGrant:
        assert token == self.launch_token
        assert user_id == self.user_id
        self.exchanges.append((token, user_id, login_device))
        return ViewerGrant(
            self.viewer_token,
            datetime.now(UTC) + timedelta(minutes=10),
        )

    def viewer_state(self, token: str) -> ViewerState:
        assert token == self.viewer_token
        return ViewerState(
            RemoteAuthStatus.READY,
            datetime.now(UTC) + timedelta(minutes=10),
            websocket_path="/websockify",
            websocket_token="websocket-secret",
            message="Ready",
        )

    def detach(self, token: str) -> bool:
        self.detached.append(token)
        return True

    def cancel(self, token: str) -> bool:
        assert token == self.viewer_token
        self.cancelled.append(token)
        return True


class StubVerifier:
    def __init__(self) -> None:
        self.calls: list[tuple[str, int]] = []

    def verify(self, init_data: str, expected_user_id: int) -> TelegramMiniAppIdentity:
        self.calls.append((init_data, expected_user_id))
        if init_data != "signed-telegram-data":
            raise ValueError("bad signature")
        return TelegramMiniAppIdentity(expected_user_id, datetime.now(UTC))


def _app(tmp_path: Path) -> tuple[RemoteAuthHttpApp, StubManager, StubVerifier]:
    manager = StubManager()
    verifier = StubVerifier()
    settings = RemoteAuthSettings(
        enabled=True,
        public_url="https://connect.example.test",
        novnc_root=tmp_path,
    )
    app = RemoteAuthHttpApp(
        settings,
        manager,  # type: ignore[arg-type]
        verifier,  # type: ignore[arg-type]
    )
    return app, manager, verifier


def _headers(response: object) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    for key, value in response.headers:  # type: ignore[attr-defined]
        result.setdefault(key.lower(), []).append(value)
    return result


def _csp_directive(csp: str, name: str) -> str:
    return next(
        directive.strip()
        for directive in csp.split(";")
        if directive.strip().startswith(f"{name} ")
    )


def test_bootstrap_is_locked_down_and_never_cacheable(tmp_path: Path) -> None:
    app, _manager, _verifier = _app(tmp_path)
    response = app.handle("GET", "/connect/launch-secret", {})
    headers = _headers(response)

    assert response.status == 200
    assert b"launch-secret" in response.body
    assert headers["cache-control"] == ["no-store"]
    assert headers["referrer-policy"] == ["no-referrer"]
    assert headers["x-frame-options"] == ["DENY"]
    csp = headers["content-security-policy"][0]
    assert "default-src 'none'" in csp
    assert "connect-src 'self' wss://connect.example.test" in csp
    assert _csp_directive(csp, "img-src") == "img-src data:"


def test_bootstrap_reports_safe_viewer_connection_failures(tmp_path: Path) -> None:
    app, _manager, _verifier = _app(tmp_path)
    response = app.handle("GET", "/connect/launch-secret", {})
    body = response.body.decode()

    assert "current.addEventListener('connect'" in body
    assert "current.addEventListener('securityfailure'" in body
    assert "current.addEventListener('disconnect'" in body
    assert "The remote browser connection failed." in body
    assert "The remote browser connection was lost." in body
    assert "Return to Telegram and try /connect again." in body
    assert "terminalState=terminalStatuses.has(state.status)" in body
    assert "if(!viewerError||terminalState||finalizing)setStatus(state.message)" in body
    assert "if(terminalState)return;" in body
    assert "event.detail.reason" not in body


def test_bootstrap_exposes_safe_touch_keyboard_and_viewport_controls(tmp_path: Path) -> None:
    app, _manager, _verifier = _app(tmp_path)
    body = app.handle("GET", "/connect/launch-secret", {}).body.decode()

    assert 'id="capture" type="password"' in body
    # Local fields never autofill saved passwords; they only advertise one-time-code hints so a
    # phone keyboard may suggest a verification code from Messages, Mail or notifications.
    assert 'autocomplete="off"' not in body
    assert body.count('autocomplete="one-time-code"') == 2
    assert 'autocorrect="off"' in body
    assert 'id="keyboard"' in body
    assert 'id="next"' in body
    assert 'id="enter"' in body
    assert "navigator.maxTouchPoints>0" in body
    assert "matchMedia('(pointer:coarse)')" in body
    assert "tg.viewportStableHeight||tg.viewportHeight" in body
    assert "window.visualViewport" in body
    assert "KeyTable.XK_BackSpace" in body
    assert "KeyTable.XK_Tab" in body
    assert "KeyTable.XK_Return" in body
    assert "keysyms.lookup" in body
    assert 'id="paste-value" type="password"' in body
    assert "navigator.clipboard.readText()" in body
    assert "clipboardPasteFrom" not in body
    assert "clipboard.write" not in body
    assert "localStorage" not in body
    assert "sessionStorage" not in body
    assert "<textarea" not in body.lower()


def test_bootstrap_detaches_on_pagehide_and_resumes_on_return(tmp_path: Path) -> None:
    app, _manager, _verifier = _app(tmp_path)
    body = app.handle("GET", "/connect/launch-secret", {}).body.decode()

    # Leaving the page detaches (grace period); only the Cancel button cancels.
    assert "window.addEventListener('pagehide',detachOnClose)" in body
    assert "fetch('/api/connect/detach'" in body
    assert "'pagehide',cancelOnClose" not in body
    assert "event&&event.persisted" in body
    assert "keepalive:true" in body
    assert "window.addEventListener('pageshow',resumeOnReturn)" in body
    assert "document.addEventListener('visibilitychange',resumeOnReturn)" in body
    assert "viewerAuthorized||terminalState||closeRequested" in body
    # A reloaded page resumes its viewer session before spending the launch link.
    assert "await jsonRequest('/api/connect/session');resumed=true" in body
    assert "state.status==='finalizing'" in body
    assert "cancelButton.disabled=true" in body
    assert "typeof tg.close==='function'" in body


def test_bootstrap_uses_packaged_novnc_input_modules(tmp_path: Path) -> None:
    app, _manager, _verifier = _app(tmp_path)
    body = app.handle("GET", "/connect/launch-secret", {}).body.decode()

    assert "import('/novnc/core/rfb.js')" in body
    assert "import('/novnc/core/input/keyboard.js')" in body
    assert "import('/novnc/core/input/keysym.js')" in body
    assert "import('/novnc/core/input/keysymdef.js')" in body
    assert "new modules.Keyboard(captureNode)" in body
    assert "compositionstart" in body
    assert "compositionend" in body


def test_exchange_requires_exact_origin_and_sets_hardened_cookie(tmp_path: Path) -> None:
    app, _manager, verifier = _app(tmp_path)
    payload = json.dumps(
        {
            "launch_token": "launch-secret",
            "init_data": "signed-telegram-data",
        }
    ).encode()

    denied = app.handle("POST", "/api/connect/exchange", {}, payload)
    assert denied.status == 401
    assert verifier.calls == []

    response = app.handle(
        "POST",
        "/api/connect/exchange",
        {"origin": "https://connect.example.test"},
        payload,
    )
    assert response.status == 200
    assert verifier.calls == [("signed-telegram-data", 123)]
    cookie = _headers(response)["set-cookie"][0]
    assert cookie.startswith("booksaver_auth=viewer-secret;")
    assert "Secure" in cookie
    assert "HttpOnly" in cookie
    assert "SameSite=Strict" in cookie
    assert "Max-Age" not in cookie


def test_detach_requires_same_origin_and_cookie(tmp_path: Path) -> None:
    app, manager, _verifier = _app(tmp_path)
    assert app.handle("POST", "/api/connect/detach", {}).status == 401
    headers = {"origin": "https://connect.example.test"}
    assert app.handle("POST", "/api/connect/detach", headers).status == 401
    headers["cookie"] = "booksaver_auth=viewer-secret"
    response = app.handle("POST", "/api/connect/detach", headers)
    assert response.status == 200
    assert json.loads(response.body) == {"status": "detached"}
    assert manager.detached == ["viewer-secret"]
    assert "viewer-secret" not in response.body.decode()


def test_viewer_and_cancel_require_cookie_and_never_echo_it(tmp_path: Path) -> None:
    app, manager, _verifier = _app(tmp_path)
    assert app.handle("GET", "/api/connect/session", {}).status == 401

    headers = {"cookie": "booksaver_auth=viewer-secret"}
    response = app.handle("GET", "/api/connect/session", headers)
    payload = json.loads(response.body)
    assert payload["status"] == "ready"
    assert payload["websocket_path"] == "/websockify"
    assert payload["websocket_token"] == "websocket-secret"
    assert b"viewer-secret" not in response.body

    assert app.handle("POST", "/api/connect/cancel", headers).status == 401
    cancelled = app.handle(
        "POST",
        "/api/connect/cancel",
        {**headers, "origin": "https://connect.example.test"},
    )
    assert cancelled.status == 200
    assert manager.cancelled == ["viewer-secret"]


def test_novnc_static_handler_blocks_traversal(tmp_path: Path) -> None:
    (tmp_path / "core").mkdir()
    (tmp_path / "core" / "rfb.js").write_text("export default class RFB {}")
    secret = tmp_path.parent / "outside.txt"
    secret.write_text("not public")
    app, _manager, _verifier = _app(tmp_path)

    response = app.handle("GET", "/novnc/core/rfb.js", {})
    assert response.status == 200
    assert response.body.startswith(b"export default")
    assert _headers(response)["cache-control"] == ["no-store"]
    assert app.handle("GET", "/novnc/../outside.txt", {}).status == 404


@pytest.mark.parametrize(
    ("hint", "expected"),
    [
        ("desktop", LoginDevice.DESKTOP),
        ("mobile", LoginDevice.MOBILE),
        (None, LoginDevice.MOBILE),
        ("Desktop", LoginDevice.MOBILE),
        ("firefox", LoginDevice.MOBILE),
        ("--no-sandbox", LoginDevice.MOBILE),
        ({"viewport": {"width": 99999}}, LoginDevice.MOBILE),
        (["desktop"], LoginDevice.MOBILE),
        (True, LoginDevice.MOBILE),
    ],
)
def test_exchange_accepts_only_allowlisted_device_hints(
    tmp_path: Path, hint: object, expected: LoginDevice,
) -> None:
    app, manager, verifier = _app(tmp_path)
    payload = json.dumps({
        "launch_token": "launch-secret",
        "init_data": "signed-telegram-data",
        "login_device": hint,
        "user_agent": "untrusted browser identity",
        "viewport": {"width": 99999, "height": 99999},
    }).encode()

    response = app.handle(
        "POST", "/api/connect/exchange",
        {"origin": "https://connect.example.test"}, payload,
    )

    assert response.status == 200
    assert verifier.calls == [("signed-telegram-data", 123)]
    assert manager.exchanges == [("launch-secret", 123, expected)]


def test_exchange_without_device_hint_preserves_mobile_clients(tmp_path: Path) -> None:
    app, manager, _verifier = _app(tmp_path)
    response = app.handle(
        "POST", "/api/connect/exchange",
        {"origin": "https://connect.example.test"},
        json.dumps({"launch_token": "launch-secret", "init_data": "signed-telegram-data"}).encode(),
    )
    assert response.status == 200
    assert manager.exchanges == [("launch-secret", 123, LoginDevice.MOBILE)]


@pytest.mark.parametrize("token,init_data", [
    ("launch-secret", "forged-telegram-data"),
    ("unknown-launch", "signed-telegram-data"),
])
def test_device_hint_cannot_bypass_launch_or_telegram_identity(
    tmp_path: Path, token: str, init_data: str,
) -> None:
    app, manager, _verifier = _app(tmp_path)
    response = app.handle(
        "POST", "/api/connect/exchange",
        {"origin": "https://connect.example.test"},
        json.dumps({
            "launch_token": token, "init_data": init_data, "login_device": "desktop",
        }).encode(),
    )
    assert response.status == 401
    assert manager.exchanges == []
