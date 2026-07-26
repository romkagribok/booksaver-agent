from __future__ import annotations

import json
import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
from playwright.sync_api import Browser, Page, sync_playwright

from booksaver.infrastructure.remote_auth.viewer import build_viewer_document

_RFB_MODULE = """
export default class RFB extends EventTarget {
  constructor(target, url) {
    super();
    this.target = target;
    this.url = url;
    this.keys = [];
    this.focusOnClick = true;
    window.__rfbInstances = window.__rfbInstances || [];
    window.__rfbInstances.push(this);
    setTimeout(() => this.dispatchEvent(new Event('connect')), 0);
  }
  sendKey(...args) { this.keys.push(args); }
  disconnect() {
    this.dispatchEvent(new CustomEvent('disconnect', {detail: {clean: true}}));
  }
  forceDirtyDisconnect() {
    this.dispatchEvent(new CustomEvent('disconnect', {detail: {clean: false}}));
  }
}
"""

_KEYBOARD_MODULE = """
export default class Keyboard {
  constructor(target) { this.target = target; this.onkeyevent = () => {}; }
  grab() { this.grabbed = true; }
  ungrab() { this.grabbed = false; }
}
"""

_KEY_TABLE_MODULE = """
export default {XK_BackSpace: 65288, XK_Tab: 65289, XK_Return: 65293};
"""

_KEYSYM_DEFINITIONS_MODULE = """
export default {lookup(value) { return value; }};
"""


class _ViewerHandler(BaseHTTPRequestHandler):
    server: _ViewerServer

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/":
            html = build_viewer_document("launch-token", "test-nonce").decode()
            html = html.replace(
                "https://telegram.org/js/telegram-web-app.js?63",
                "/telegram.js",
            )
            self._send(200, html, "text/html; charset=utf-8")
            return
        if self.path == "/telegram.js":
            platform = json.dumps(self.server.platform)
            self._send(
                200,
                "window.Telegram={WebApp:{"
                "initData:'signed',"
                f"platform:{platform},"
                "viewportHeight:780,viewportStableHeight:780,"
                "ready(){},expand(){},onEvent(){},close(){window.__telegramClosed=true;}"
                "}};",
                "text/javascript",
            )
            return
        modules = {
            "/novnc/core/rfb.js": _RFB_MODULE,
            "/novnc/core/input/keyboard.js": _KEYBOARD_MODULE,
            "/novnc/core/input/keysym.js": _KEY_TABLE_MODULE,
            "/novnc/core/input/keysymdef.js": _KEYSYM_DEFINITIONS_MODULE,
        }
        if self.path in modules:
            self._send(200, modules[self.path], "text/javascript")
            return
        if self.path == "/api/connect/session":
            payload = {
                "status": self.server.session_status,
                "message": "Ready" if self.server.session_status == "ready" else "Done",
                "expires_at": "2026-07-27T00:00:00+00:00",
                "websocket_path": "/websockify",
                "websocket_token": "ws-token",
            }
            self._send(200, json.dumps(payload), "application/json")
            return
        self._send(404, "not found", "text/plain")

    def do_POST(self) -> None:  # noqa: N802
        length = int(self.headers.get("Content-Length", "0"))
        if length:
            self.rfile.read(length)
        if self.path == "/api/connect/exchange":
            self.server.exchanges += 1
            self._send(200, '{"status":"authorized"}', "application/json")
            return
        if self.path == "/api/connect/cancel":
            self.server.cancellations += 1
            self._send(200, '{"status":"cancelled"}', "application/json")
            return
        self._send(404, "not found", "text/plain")

    def _send(self, status: int, body: str, content_type: str) -> None:
        encoded = body.encode()
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def log_message(self, _format: str, *args: object) -> None:
        return


class _ViewerServer(ThreadingHTTPServer):
    platform: str
    session_status: str
    exchanges: int
    cancellations: int


@pytest.fixture
def viewer_server() -> Iterator[tuple[_ViewerServer, str]]:
    server = _ViewerServer(("127.0.0.1", 0), _ViewerHandler)
    server.platform = "android"
    server.session_status = "ready"
    server.exchanges = 0
    server.cancellations = 0
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        yield server, f"http://127.0.0.1:{server.server_port}/"
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=2)


@pytest.fixture(scope="module")
def browser() -> Iterator[Browser]:
    with sync_playwright() as playwright:
        try:
            browser = playwright.chromium.launch(headless=True)
        except Exception as exc:
            pytest.skip(f"Playwright Chromium is unavailable: {type(exc).__name__}")
        try:
            yield browser
        finally:
            browser.close()


@pytest.fixture
def browser_page(browser: Browser) -> Iterator[Page]:
    context = browser.new_context(has_touch=True, viewport={"width": 390, "height": 780})
    page = context.new_page()
    try:
        yield page
    finally:
        context.close()


@pytest.fixture
def desktop_page(browser: Browser) -> Iterator[Page]:
    context = browser.new_context(has_touch=False, viewport={"width": 1000, "height": 700})
    page = context.new_page()
    try:
        yield page
    finally:
        context.close()


def test_touch_viewer_forwards_mobile_input_and_shortcuts(
    viewer_server: tuple[_ViewerServer, str],
    browser_page: Page,
) -> None:
    server, url = viewer_server
    browser_page.goto(url)
    browser_page.locator("#keyboard").wait_for(state="visible")
    browser_page.wait_for_function("!document.querySelector('#keyboard').disabled")

    assert server.exchanges == 1
    assert browser_page.locator("body").evaluate(
        "element => element.classList.contains('touch-first')"
    )

    browser_page.locator("#keyboard").click()
    assert browser_page.evaluate("document.activeElement.id") == "capture"
    assert browser_page.locator("#keyboard").get_attribute("aria-pressed") == "true"
    browser_page.locator("#viewer").dispatch_event(
        "pointerdown",
        {"clientX": 100, "clientY": 700},
    )
    browser_page.evaluate(
        """() => {
          Object.defineProperty(window.visualViewport, 'height', {
            configurable: true, get: () => 360
          });
          window.visualViewport.dispatchEvent(new Event('resize'));
        }"""
    )
    browser_page.wait_for_function(
        "getComputedStyle(document.documentElement).getPropertyValue('--app-height') === '360px'"
    )
    browser_page.wait_for_function("document.querySelector('#viewer').scrollTop > 0")

    browser_page.locator("#capture").evaluate(
        """element => {
          element.value += 'A';
          element.setSelectionRange(element.value.length, element.value.length);
          element.dispatchEvent(new InputEvent('input', {bubbles: true}));
        }"""
    )
    assert not browser_page.locator("#capture").input_value().endswith("A")
    browser_page.locator("#capture").evaluate(
        """element => {
          element.dispatchEvent(new CompositionEvent('compositionstart', {bubbles: true}));
          element.value += 'é';
          element.setSelectionRange(element.value.length, element.value.length);
          element.dispatchEvent(new InputEvent('input', {
            bubbles: true, inputType: 'insertCompositionText', data: 'é'
          }));
          element.dispatchEvent(new CompositionEvent('compositionend', {
            bubbles: true, data: 'é'
          }));
        }"""
    )
    assert not browser_page.locator("#capture").input_value().endswith("é")
    browser_page.locator("#capture").evaluate(
        """element => {
          element.value = element.value.slice(0, -1);
          element.setSelectionRange(element.value.length, element.value.length);
          element.dispatchEvent(new InputEvent('input', {bubbles: true}));
        }"""
    )
    browser_page.locator("#next").click()
    browser_page.locator("#enter").click()

    keys = browser_page.evaluate("window.__rfbInstances[0].keys")
    assert keys[-5:] == [
        [65],
        [233],
        [65288, "Backspace"],
        [65289, "Tab"],
        [65293, "Enter"],
    ]
    assert browser_page.evaluate("document.activeElement.id") == "capture"

    browser_page.locator("#keyboard").click()
    assert not browser_page.locator("body").evaluate(
        "element => element.classList.contains('keyboard-open')"
    )
    assert browser_page.locator("#keyboard").inner_text() == "Keyboard"
    assert browser_page.evaluate("document.activeElement.id") != "capture"

    browser_page.locator("#keyboard").click()
    assert browser_page.locator("body").evaluate(
        "element => element.classList.contains('keyboard-open')"
    )
    assert browser_page.locator("#keyboard").inner_text() == "Hide keyboard"
    assert browser_page.evaluate("document.activeElement.id") == "capture"


def test_platform_fallbacks_and_bounded_rfb_reconnect(
    viewer_server: tuple[_ViewerServer, str],
    desktop_page: Page,
) -> None:
    server, url = viewer_server
    server.platform = "unknown"
    desktop_page.goto(url)
    desktop_page.wait_for_function("!document.querySelector('#keyboard').disabled")

    assert not desktop_page.locator("body").evaluate(
        "element => element.classList.contains('touch-first')"
    )
    assert desktop_page.locator("#help").is_hidden()
    assert desktop_page.locator("#help-button").is_hidden()
    assert desktop_page.locator("#keyboard").is_visible()
    assert desktop_page.evaluate("window.__rfbInstances[0].focusOnClick") is True

    desktop_page.evaluate("window.__rfbInstances[0].forceDirtyDisconnect()")
    desktop_page.wait_for_function("window.__rfbInstances.length === 2")
    desktop_page.wait_for_function("!document.querySelector('#keyboard').disabled")

    desktop_page.evaluate("window.__rfbInstances[1].forceDirtyDisconnect()")
    desktop_page.wait_for_timeout(1200)
    assert desktop_page.evaluate("window.__rfbInstances.length") == 2
    assert "try /connect again" in desktop_page.locator("#status").inner_text()

    server.platform = "ios"
    desktop_page.goto(url)
    desktop_page.wait_for_function("!document.querySelector('#keyboard').disabled")
    assert desktop_page.locator("body").evaluate(
        "element => element.classList.contains('touch-first')"
    )


def test_pagehide_cancels_best_effort_and_visibility_change_does_not(
    viewer_server: tuple[_ViewerServer, str],
    browser_page: Page,
) -> None:
    server, url = viewer_server
    browser_page.goto(url)
    browser_page.wait_for_function("!document.querySelector('#keyboard').disabled")

    browser_page.evaluate("document.dispatchEvent(new Event('visibilitychange'))")
    browser_page.wait_for_timeout(50)
    assert server.cancellations == 0

    browser_page.evaluate(
        "window.dispatchEvent(new PageTransitionEvent('pagehide', {persisted: true}))"
    )
    browser_page.wait_for_timeout(50)
    assert server.cancellations == 0

    browser_page.evaluate(
        "window.dispatchEvent(new PageTransitionEvent('pagehide', {persisted: false}))"
    )
    browser_page.wait_for_function(
        "() => true",
        timeout=100,
    )
    for _ in range(20):
        if server.cancellations:
            break
        browser_page.wait_for_timeout(25)
    assert server.cancellations == 1


def test_terminal_viewer_disables_input_and_does_not_cancel_on_close(
    viewer_server: tuple[_ViewerServer, str],
    browser_page: Page,
) -> None:
    server, url = viewer_server
    server.session_status = "succeeded"
    browser_page.goto(url)
    browser_page.wait_for_function(
        "document.querySelector('#status').textContent === 'Done'"
    )

    assert browser_page.locator("#keyboard").is_disabled()
    browser_page.evaluate(
        "window.dispatchEvent(new PageTransitionEvent('pagehide', {persisted: false}))"
    )
    browser_page.wait_for_timeout(50)
    assert server.cancellations == 0
