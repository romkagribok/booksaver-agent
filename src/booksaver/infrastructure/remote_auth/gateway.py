from __future__ import annotations

import json
import mimetypes
import secrets
import threading
from dataclasses import dataclass
from datetime import UTC, datetime
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
        token_json = json.dumps(launch_token)
        html = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1,user-scalable=no">
<title>Connect Booking.com</title>
<script src="https://telegram.org/js/telegram-web-app.js?63"></script>
<style nonce="{nonce}">
html,body{{margin:0;height:100%;background:#101820;color:#fff;font:16px system-ui,sans-serif}}
body{{display:flex;flex-direction:column}}#status{{padding:12px 16px;background:#182633}}
#screen{{flex:1;min-height:0;overflow:hidden;background:#000}}button{{margin:10px;padding:12px}}
</style></head><body><div id="status">Authorizing this connection…</div>
<div id="screen"></div><button id="cancel" type="button">Cancel</button>
<script nonce="{nonce}">
const launchToken={token_json}; let rfb=null; let terminalState=false; let viewerError=false;
const terminalStatuses=new Set(['succeeded','failed','expired','cancelled']);
const statusNode=document.getElementById('status');
const tg=window.Telegram&&window.Telegram.WebApp; if(tg){{tg.ready();tg.expand();}}
function setViewerError(message){{
 if(terminalState)return; viewerError=true; statusNode.textContent=message;
}}
async function jsonRequest(url,options={{}}){{
 const response=await fetch(url,{{credentials:'same-origin',...options}});
 const data=await response.json().catch(()=>({{message:'Connection unavailable.'}}));
 if(!response.ok) throw new Error(data.message||'Connection unavailable.'); return data;
}}
async function poll(){{
 try{{const state=await jsonRequest('/api/connect/session');
  terminalState=terminalStatuses.has(state.status);
  if(!viewerError||terminalState)statusNode.textContent=state.message;
  if((state.status==='ready'||state.status==='connected')&&!rfb){{
   const module=await import('/novnc/core/rfb.js');
   const scheme=location.protocol==='https:'?'wss':'ws';
   const ws=`${{scheme}}://${{location.host}}${{state.websocket_path}}?token=${{encodeURIComponent(state.websocket_token)}}`;
   rfb=new module.default(document.getElementById('screen'),ws);
   rfb.addEventListener('connect',()=>{{
    if(!terminalState){{viewerError=false;statusNode.textContent='Remote browser connected.';}}
   }});
   rfb.addEventListener('securityfailure',()=>setViewerError(
    'The remote browser connection failed. Return to Telegram and try /connect again.'));
   rfb.addEventListener('disconnect',event=>{{
    if(event.detail&&event.detail.clean===false)setViewerError(
     'The remote browser connection was lost. Return to Telegram and try /connect again.');
   }});
   rfb.scaleViewport=true; rfb.resizeSession=false; rfb.showDotCursor=true;
  }}
  if(terminalState){{if(rfb)rfb.disconnect();return;}}
  setTimeout(poll,1000);
 }}catch(error){{statusNode.textContent=error.message;}}
}}
async function start(){{
 if(!tg||!tg.initData)throw new Error(
  'Open this page from the button in your private Telegram chat.');
 await jsonRequest('/api/connect/exchange',{{method:'POST',
  headers:{{'Content-Type':'application/json'}},
  body:JSON.stringify({{launch_token:launchToken,init_data:tg.initData}})}}); await poll();
}}
document.getElementById('cancel').addEventListener('click',async()=>{{
 try{{await jsonRequest('/api/connect/cancel',{{method:'POST'}});}}catch(_){{}} if(tg)tg.close();
}});
start().catch(error=>{{statusNode.textContent=error.message;}});
</script></body></html>""".encode()
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
        max_age = max(0, int((grant.expires_at - datetime.now(UTC)).total_seconds()))
        cookie = (
            f"{_COOKIE_NAME}={grant.session_token}; Path=/; Max-Age={max_age}; "
            "Secure; HttpOnly; SameSite=Strict"
        )
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
