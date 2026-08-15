from __future__ import annotations

import json
import mimetypes
import secrets
import threading
from dataclasses import dataclass
from http import HTTPStatus
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import urlparse

from booksaver.application.remote_auth import (
    RemoteAuthDenied,
    RemoteAuthenticationManager,
)
from booksaver.domain.remote_auth import RemoteAuthSettings

from .telegram_init_data import TelegramInitDataError, TelegramInitDataVerifier
from .viewer import build_viewer_document

_MAX_BODY_BYTES = 32_768
_COOKIE_NAME = "booksaver_auth"


@dataclass(frozen=True)
class HttpResponse:
    status: int
    body: bytes
    content_type: str
    headers: tuple[tuple[str, str], ...] = ()


class RemoteAuthHttpApp:
    def __init__(
        self,
        settings: RemoteAuthSettings,
        manager: RemoteAuthenticationManager,
        verifier: TelegramInitDataVerifier,
    ) -> None:
        self._settings = settings
        self._manager = manager
        self._verifier = verifier
        parsed = urlparse(settings.base_url)
        self._expected_origin = f"{parsed.scheme}://{parsed.netloc}"

    def handle(
        self,
        method: str,
        path: str,
        headers: dict[str, str],
        body: bytes = b"",
    ) -> HttpResponse:
        route_path = urlparse(path).path
        if method == "GET" and route_path == "/healthz":
            return self._response(HTTPStatus.OK, b"ok\n", "text/plain; charset=utf-8")
        if method == "GET" and route_path.startswith("/connect/"):
            launch_token = route_path.removeprefix("/connect/")
            if not launch_token or "/" in launch_token or len(launch_token) > 128:
                return self._not_found()
            return self._bootstrap(launch_token)
        if method == "GET" and route_path.startswith("/novnc/"):
            return self._static_novnc(route_path.removeprefix("/novnc/"))
        if method == "POST" and route_path == "/api/connect/exchange":
            if not self._same_origin(headers):
                return self._denied()
            return self._exchange(body)
        if method == "GET" and route_path == "/api/connect/session":
            return self._session(headers)
        if method == "POST" and route_path == "/api/connect/cancel":
            if not self._same_origin(headers):
                return self._denied()
            return self._cancel(headers)
        return self._not_found()

    def _bootstrap(self, launch_token: str) -> HttpResponse:
        nonce = secrets.token_urlsafe(18)
        html = build_viewer_document(launch_token, nonce)
        websocket_origin = self._expected_origin.replace("https:", "wss:")
        csp = (
            "default-src 'none'; base-uri 'none'; frame-ancestors 'none'; "
            f"script-src 'self' https://telegram.org 'nonce-{nonce}'; "
            f"style-src 'nonce-{nonce}'; connect-src 'self' {websocket_origin}; "
            "img-src data:; font-src 'none'; form-action 'none'"
        )
        return self._response(
            HTTPStatus.OK,
            html,
            "text/html; charset=utf-8",
            (("Content-Security-Policy", csp),),
        )

    def _exchange(self, body: bytes) -> HttpResponse:
        if len(body) > _MAX_BODY_BYTES:
            return self._denied()
        try:
            data: dict[str, Any] = json.loads(body.decode("utf-8"))
            launch_token = str(data["launch_token"])
            init_data = str(data["init_data"])
            expected_user = self._manager.expected_telegram_user(launch_token)
            identity = self._verifier.verify(init_data, expected_user)
            grant = self._manager.exchange(launch_token, identity.telegram_user_id)
        except (
            KeyError,
            TypeError,
            ValueError,
            UnicodeDecodeError,
            json.JSONDecodeError,
            TelegramInitDataError,
            RemoteAuthDenied,
        ):
            return self._denied()
        cookie = f"{_COOKIE_NAME}={grant.session_token}; Path=/; Secure; HttpOnly; SameSite=Strict"
        return self._json(
            HTTPStatus.OK,
            {"status": "authorized"},
            (("Set-Cookie", cookie),),
        )

    def _session(self, headers: dict[str, str]) -> HttpResponse:
        token = self._cookie_token(headers)
        if token is None:
            return self._denied()
        try:
            state = self._manager.viewer_state(token)
        except RemoteAuthDenied:
            return self._denied()
        return self._json(
            HTTPStatus.OK,
            {
                "status": state.status.value,
                "message": state.message,
                "expires_at": state.expires_at.isoformat(),
                "websocket_path": state.websocket_path,
                "websocket_token": state.websocket_token,
            },
        )

    def _cancel(self, headers: dict[str, str]) -> HttpResponse:
        token = self._cookie_token(headers)
        if token is None:
            return self._denied()
        try:
            self._manager.cancel(token)
        except RemoteAuthDenied:
            return self._denied()
        return self._json(HTTPStatus.OK, {"status": "cancelled"})

    def _static_novnc(self, relative: str) -> HttpResponse:
        root = self._settings.novnc_root.resolve()
        try:
            target = (root / relative).resolve()
            target.relative_to(root)
        except (OSError, ValueError):
            return self._not_found()
        if not target.is_file():
            return self._not_found()
        try:
            body = target.read_bytes()
        except OSError:
            return self._not_found()
        content_type = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
        return self._response(
            HTTPStatus.OK,
            body,
            content_type,
        )

    def _same_origin(self, headers: dict[str, str]) -> bool:
        return headers.get("origin") == self._expected_origin

    @staticmethod
    def _cookie_token(headers: dict[str, str]) -> str | None:
        cookie = SimpleCookie()
        try:
            cookie.load(headers.get("cookie", ""))
        except Exception:
            return None
        morsel = cookie.get(_COOKIE_NAME)
        return morsel.value if morsel is not None else None

    def _denied(self) -> HttpResponse:
        return self._json(
            HTTPStatus.UNAUTHORIZED,
            {"message": "This connection is invalid or expired."},
        )

    def _not_found(self) -> HttpResponse:
        return self._json(HTTPStatus.NOT_FOUND, {"message": "Not found."})

    def _json(
        self,
        status: int,
        payload: dict[str, Any],
        headers: tuple[tuple[str, str], ...] = (),
    ) -> HttpResponse:
        return self._response(
            status,
            json.dumps(payload, separators=(",", ":")).encode("utf-8"),
            "application/json; charset=utf-8",
            headers,
        )

    @staticmethod
    def _response(
        status: int,
        body: bytes,
        content_type: str,
        headers: tuple[tuple[str, str], ...] = (),
    ) -> HttpResponse:
        security_headers = (
            ("Cache-Control", "no-store"),
            ("Referrer-Policy", "no-referrer"),
            ("X-Content-Type-Options", "nosniff"),
            ("X-Frame-Options", "DENY"),
            ("Permissions-Policy", "camera=(), microphone=(), geolocation=()"),
        )
        return HttpResponse(int(status), body, content_type, security_headers + headers)


class _RequestHandler(BaseHTTPRequestHandler):
    server: _RemoteAuthServer

    def do_GET(self) -> None:  # noqa: N802 - stdlib handler API
        self._dispatch("GET")

    def do_POST(self) -> None:  # noqa: N802 - stdlib handler API
        self._dispatch("POST")

    def _dispatch(self, method: str) -> None:
        length_text = self.headers.get("Content-Length", "0")
        try:
            length = int(length_text)
        except ValueError:
            length = _MAX_BODY_BYTES + 1
        body = self.rfile.read(length) if 0 <= length <= _MAX_BODY_BYTES else b""
        headers = {key.lower(): value for key, value in self.headers.items()}
        response = self.server.app.handle(method, self.path, headers, body)
        self.send_response(response.status)
        self.send_header("Content-Type", response.content_type)
        self.send_header("Content-Length", str(len(response.body)))
        for key, value in response.headers:
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(response.body)

    def log_message(self, _format: str, *args: object) -> None:
        # Request paths contain short-lived capabilities. Never log them.
        return


class _RemoteAuthServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address: tuple[str, int], app: RemoteAuthHttpApp) -> None:
        self.app = app
        super().__init__(address, _RequestHandler)


class RemoteAuthGatewayRunner:
    def __init__(self, settings: RemoteAuthSettings, app: RemoteAuthHttpApp) -> None:
        self._settings = settings
        self._app = app

    def run(self, stop_event: threading.Event) -> None:
        server = _RemoteAuthServer(
            (self._settings.listen_host, self._settings.listen_port), self._app
        )
        server.timeout = 0.5
        try:
            while not stop_event.is_set():
                server.handle_request()
        finally:
            server.server_close()
