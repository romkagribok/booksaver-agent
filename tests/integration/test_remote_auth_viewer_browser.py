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
  blur() { this.blurs = (this.blurs || 0) + 1; }
  focus() { this.focuses = (this.focuses || 0) + 1; }
  disconnect() {
    this.disconnected = true;
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

_TELEGRAM_MODULE = """
const options = __OPTIONS__;
const handlers = {};
window.__fullscreenRequests = 0;
window.__fullscreenExits = 0;
window.__expandRequests = 0;
window.__telegramEvent = (name, data) => {
  for (const callback of handlers[name] || []) callback(data);
};
const app = {
  initData: 'signed', platform: options.platform,
  viewportHeight: 780, viewportStableHeight: 780,
  ready() {}, expand() { window.__expandRequests++; },
  onEvent(name, callback) { (handlers[name] ||= []).push(callback); },
  close() { window.__telegramClosed = true; }
};
if (options.hostClipboard !== 'missing') {
  window.__hostReads = 0;
  app.isVersionAtLeast = app.isVersionAtLeast || (() => true);
  app.readTextFromClipboard = (callback) => {
    window.__hostReads++;
    if (options.hostClipboard === 'silent') return;
    setTimeout(() => callback(options.hostClipboard === 'null' ? null : options.hostClipboard), 0);
  };
}
if (options.fullscreen !== 'missing') {
  app.isFullscreen = options.fullscreen === 'already';
  app.isVersionAtLeast = () => options.fullscreen !== 'old';
  app.requestFullscreen = () => {
    window.__fullscreenRequests++;
    if (options.fullscreen === 'throw') throw new Error('Host unavailable');
    if (options.fullscreen === 'unsupported') {
      setTimeout(() => window.__telegramEvent('fullscreenFailed', {error: 'UNSUPPORTED'}), 0);
      return;
    }
    app.isFullscreen = true;
    window.__telegramEvent('fullscreenChanged');
  };
  app.exitFullscreen = () => {
    window.__fullscreenExits++;
    app.isFullscreen = false;
    window.__telegramEvent('fullscreenChanged');
  };
}
window.Telegram = {WebApp: app};
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
            options = json.dumps(
                {
                    "platform": self.server.platform,
                    "fullscreen": self.server.fullscreen_mode,
                    "hostClipboard": self.server.host_clipboard,
                }
            )
            self._send(
                200,
                _TELEGRAM_MODULE.replace("__OPTIONS__", options),
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
        body = self.rfile.read(length) if length else b"{}"
        if self.path == "/api/connect/exchange":
            self.server.exchange_payloads.append(json.loads(body))
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
    fullscreen_mode: str
    host_clipboard: str
    session_status: str
    exchanges: int
    exchange_payloads: list[dict[str, object]]
    cancellations: int


@pytest.fixture
def viewer_server() -> Iterator[tuple[_ViewerServer, str]]:
    server = _ViewerServer(("127.0.0.1", 0), _ViewerHandler)
    server.platform = "android"
    server.fullscreen_mode = "missing"
    server.host_clipboard = "missing"
    server.session_status = "ready"
    server.exchanges = 0
    server.exchange_payloads = []
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
    browser_page.wait_for_function("document.querySelector('#status').textContent === 'Done'")

    assert browser_page.locator("#keyboard").is_disabled()
    browser_page.evaluate(
        "window.dispatchEvent(new PageTransitionEvent('pagehide', {persisted: false}))"
    )
    browser_page.wait_for_timeout(50)
    assert server.cancellations == 0
    assert browser_page.evaluate("window.__telegramClosed") is True


def test_finalizing_disables_viewer_and_suppresses_pagehide_until_success(
    viewer_server: tuple[_ViewerServer, str],
    browser_page: Page,
) -> None:
    server, url = viewer_server
    browser_page.goto(url)
    browser_page.wait_for_function("!document.querySelector('#keyboard').disabled")

    server.session_status = "finalizing"
    browser_page.wait_for_function(
        "document.querySelector('#cancel').disabled && document.querySelector('#keyboard').disabled"
    )
    assert browser_page.evaluate("window.__rfbInstances[0].disconnected") is True

    browser_page.evaluate(
        "window.dispatchEvent(new PageTransitionEvent('pagehide', {persisted: false}))"
    )
    browser_page.wait_for_timeout(50)
    assert server.cancellations == 0

    server.session_status = "succeeded"
    browser_page.wait_for_function("window.__telegramClosed === true")
    assert server.cancellations == 0


def test_failed_viewer_remains_visible_and_does_not_close_telegram(
    viewer_server: tuple[_ViewerServer, str],
    browser_page: Page,
) -> None:
    server, url = viewer_server
    server.session_status = "failed"
    browser_page.goto(url)
    browser_page.wait_for_function("document.querySelector('#status').textContent === 'Done'")

    assert browser_page.evaluate("Boolean(window.__telegramClosed)") is False
    assert browser_page.locator("#cancel").is_disabled()
    browser_page.evaluate(
        "window.dispatchEvent(new PageTransitionEvent('pagehide', {persisted: false}))"
    )
    browser_page.wait_for_timeout(50)
    assert server.cancellations == 0


@pytest.mark.parametrize("platform", ["tdesktop", "macos", "unigram", "web", "unknown"])
def test_desktop_fullscreen_can_exit_reenter_and_resize_without_reconnecting(
    viewer_server: tuple[_ViewerServer, str], desktop_page: Page, platform: str
) -> None:
    server, url = viewer_server
    server.platform = platform
    server.fullscreen_mode = "success"
    desktop_page.goto(url)
    desktop_page.wait_for_function("!document.querySelector('#keyboard').disabled")
    button = desktop_page.get_by_role("button", name="Exit full screen", exact=True)
    assert button.get_attribute("aria-pressed") == "true"
    assert desktop_page.evaluate("window.__fullscreenRequests") == 1
    assert desktop_page.evaluate("window.__expandRequests") == 1

    button.click()
    button = desktop_page.get_by_role("button", name="Full screen", exact=True)
    assert button.get_attribute("aria-pressed") == "false"
    assert desktop_page.evaluate("window.__fullscreenExits") == 1
    button.click()
    assert desktop_page.evaluate("window.__fullscreenRequests") == 2

    for width, height in [(1440, 1000), (600, 480)]:
        desktop_page.set_viewport_size({"width": width, "height": height})
        desktop_page.wait_for_function("document.body.clientHeight === window.innerHeight")
        viewer = desktop_page.locator("#viewer").bounding_box()
        dock = desktop_page.locator("#dock").bounding_box()
        assert viewer is not None and dock is not None
        assert viewer["width"] == width
        assert viewer["height"] > height - 170
        assert dock["y"] + dock["height"] == height
    assert server.exchanges == 1
    assert server.cancellations == 0
    assert desktop_page.evaluate("window.__rfbInstances.length") == 1
    assert desktop_page.evaluate("window.__rfbInstances[0].scaleViewport") is True
    assert desktop_page.evaluate("window.__rfbInstances[0].resizeSession") is False


@pytest.mark.parametrize("mode", ["missing", "old", "throw", "unsupported", "already"])
def test_fullscreen_compatibility_never_blocks_login(
    viewer_server: tuple[_ViewerServer, str], desktop_page: Page, mode: str
) -> None:
    server, url = viewer_server
    server.platform = "tdesktop"
    server.fullscreen_mode = mode
    errors: list[str] = []
    desktop_page.on("pageerror", lambda error: errors.append(str(error)))
    desktop_page.goto(url)
    desktop_page.wait_for_function("!document.querySelector('#keyboard').disabled")
    assert desktop_page.evaluate("window.__fullscreenRequests") == (
        1 if mode in {"throw", "unsupported"} else 0
    )
    if mode in {"throw", "unsupported"}:
        assert desktop_page.locator("#size-hint").is_visible()
        assert "connected" in desktop_page.locator("#status").inner_text()
    if mode in {"missing", "old", "unsupported"}:
        assert desktop_page.locator("#fullscreen").is_hidden()
    # Resize/host events cannot cause an automatic retry or an authentication exchange.
    desktop_page.evaluate("window.__telegramEvent('viewportChanged')")
    desktop_page.set_viewport_size({"width": 1200, "height": 900})
    assert desktop_page.evaluate("window.__fullscreenRequests") == (
        1 if mode in {"throw", "unsupported"} else 0
    )
    assert server.exchanges == 1
    assert server.cancellations == 0
    assert errors == []


@pytest.mark.parametrize("platform", ["android", "ios", "web", "unknown", "tdesktop"])
def test_touch_fullscreen_choice_and_safe_areas(
    viewer_server: tuple[_ViewerServer, str], browser_page: Page, platform: str
) -> None:
    server, url = viewer_server
    server.platform = platform
    server.fullscreen_mode = "success"
    browser_page.goto(url)
    browser_page.wait_for_function("!document.querySelector('#keyboard').disabled")
    assert browser_page.evaluate("window.__fullscreenRequests") == (platform == "tdesktop")
    if platform != "tdesktop":
        browser_page.get_by_role("button", name="Full screen", exact=True).click()
    assert browser_page.evaluate("window.Telegram.WebApp.isFullscreen") is True

    for width, height in [(390, 780), (780, 390), (320, 568)]:
        browser_page.set_viewport_size({"width": width, "height": height})
        browser_page.evaluate(
            """() => {
              const app = window.Telegram.WebApp;
              app.safeAreaInset = {top: 24, bottom: 20, left: 12, right: 14};
              app.contentSafeAreaInset = {top: 46, bottom: 5, left: 4, right: 6};
              window.__telegramEvent('safeAreaChanged');
              window.__telegramEvent('contentSafeAreaChanged');
            }"""
        )
        browser_page.wait_for_function("document.body.clientHeight === window.innerHeight")
        assert (
            browser_page.locator("body").evaluate("element => getComputedStyle(element).paddingTop")
            == "70px"
        )
        assert browser_page.locator("#dock").evaluate(
            "element => getComputedStyle(element).paddingBottom"
        ) in {"32px", "29px"}  # Compact landscape dock uses 4px instead of 7px.
        for selector in ["#viewer", "#fullscreen", "#keyboard", "#next", "#enter", "#cancel"]:
            box = browser_page.locator(selector).bounding_box()
            assert box is not None
            assert box["x"] >= 16
            assert box["x"] + box["width"] <= width - 20
            assert box["y"] >= 70
            assert box["y"] + box["height"] <= height - 25
        viewer = browser_page.locator("#viewer").bounding_box()
        assert viewer is not None and viewer["height"] > 0
    browser_page.evaluate(
        """() => {
          window.Telegram.WebApp.safeAreaInset = {};
          window.Telegram.WebApp.contentSafeAreaInset = {};
          window.__telegramEvent('contentSafeAreaChanged');
        }"""
    )
    assert (
        browser_page.locator("body").evaluate("element => getComputedStyle(element).paddingTop")
        == "0px"
    )
    assert server.exchanges == 1
    assert server.cancellations == 0
    assert browser_page.evaluate("window.__rfbInstances.length") == 1


def test_fullscreen_mobile_keyboard_keeps_controls_and_touched_region_reachable(
    viewer_server: tuple[_ViewerServer, str], browser_page: Page
) -> None:
    server, url = viewer_server
    server.fullscreen_mode = "success"
    browser_page.goto(url)
    browser_page.wait_for_function("!document.querySelector('#keyboard').disabled")
    browser_page.get_by_role("button", name="Full screen", exact=True).click()
    browser_page.evaluate(
        """() => {
          const app = window.Telegram.WebApp;
          app.safeAreaInset = {top: 24, bottom: 20};
          app.contentSafeAreaInset = {top: 46};
          window.__telegramEvent('safeAreaChanged');
        }"""
    )
    browser_page.locator("#viewer").dispatch_event("pointerdown", {"clientY": 600})
    browser_page.locator("#keyboard").click()
    browser_page.evaluate(
        """() => {
          Object.defineProperty(window.visualViewport, 'height', {
            configurable: true, get: () => 360
          });
          window.visualViewport.dispatchEvent(new Event('resize'));
        }"""
    )
    browser_page.wait_for_function("document.querySelector('#viewer').scrollTop > 0")
    viewer = browser_page.locator("#viewer").bounding_box()
    assert viewer is not None and viewer["height"] > 0
    assert browser_page.locator("#fullscreen").is_hidden()
    for selector in ["#keyboard", "#next", "#enter", "#cancel"]:
        box = browser_page.locator(selector).bounding_box()
        assert box is not None and box["y"] + box["height"] <= 340
        assert browser_page.locator(selector).evaluate(
            "element => element.scrollWidth <= element.clientWidth"
        )
    assert browser_page.evaluate("document.activeElement.id") == "capture"
    browser_page.locator("#next").click()
    assert browser_page.evaluate("window.__rfbInstances[0].keys.at(-1)") == [65289, "Tab"]
    browser_page.locator("#keyboard").click()
    browser_page.evaluate(
        """() => {
          delete window.visualViewport.height;
          window.visualViewport.dispatchEvent(new Event('resize'));
        }"""
    )
    browser_page.wait_for_function("document.body.clientHeight === 780")
    assert browser_page.get_by_role("button", name="Exit full screen", exact=True).is_visible()
    assert browser_page.locator("#viewer").evaluate("element => element.scrollTop") == 0
    assert browser_page.evaluate("window.__rfbInstances.length") == 1
    assert server.exchanges == 1
    assert server.cancellations == 0


@pytest.mark.parametrize(
    ("platform", "has_touch", "expected"),
    [
        ("tdesktop", False, "desktop"),
        ("tdesktop", True, "desktop"),
        ("macos", True, "desktop"),
        ("unigram", True, "desktop"),
        ("android", False, "mobile"),
        ("android_x", True, "mobile"),
        ("ios", False, "mobile"),
        ("web", False, "desktop"),
        ("webk", False, "desktop"),
        ("weba", False, "desktop"),
        ("web", True, "mobile"),
        ("webk", True, "mobile"),
        ("weba", True, "mobile"),
        ("unknown", False, "mobile"),
        ("unknown", True, "mobile"),
        ("future-client", False, "mobile"),
    ],
)
def test_login_discovery_sends_only_device_class_and_remains_stable_on_resize(
    viewer_server: tuple[_ViewerServer, str],
    browser: Browser,
    platform: str,
    has_touch: bool,
    expected: str,
) -> None:
    server, url = viewer_server
    server.platform = platform
    context = browser.new_context(has_touch=has_touch, viewport={"width": 1000, "height": 700})
    try:
        page = context.new_page()
        page.goto(url)
        page.wait_for_function("!document.querySelector('#keyboard').disabled")
        assert server.exchange_payloads == [
            {"launch_token": "launch-token", "init_data": "signed", "login_device": expected}
        ]
        page.set_viewport_size({"width": 390, "height": 780})
        page.evaluate("window.__telegramEvent('viewportChanged')")
        assert server.exchanges == 1
        assert page.locator("body").evaluate(
            "element => element.classList.contains('desktop-login')"
        ) is (expected == "desktop")
    finally:
        context.close()


def test_web_discovery_without_pointer_capability_defaults_to_mobile(
    viewer_server: tuple[_ViewerServer, str], desktop_page: Page
) -> None:
    server, url = viewer_server
    server.platform = "web"
    desktop_page.add_init_script("window.matchMedia = undefined")
    desktop_page.goto(url)
    desktop_page.wait_for_function("!document.querySelector('#keyboard').disabled")
    assert server.exchange_payloads[0]["login_device"] == "mobile"


def test_touch_desktop_keyboard_uses_landscape_stream_geometry(
    viewer_server: tuple[_ViewerServer, str], browser_page: Page
) -> None:
    server, url = viewer_server
    server.platform = "tdesktop"
    browser_page.goto(url)
    browser_page.wait_for_function("!document.querySelector('#keyboard').disabled")
    browser_page.locator("#keyboard").click()
    browser_page.evaluate(
        """() => {
          Object.defineProperty(window.visualViewport, 'height', {
            configurable: true, get: () => 360
          });
          window.visualViewport.dispatchEvent(new Event('resize'));
        }"""
    )
    browser_page.wait_for_function("document.body.clientHeight === 360")
    screen = browser_page.locator("#screen").bounding_box()
    assert screen is not None
    assert screen["height"] == pytest.approx(390 * 800 / 1280)
    for selector in ["#keyboard", "#next", "#enter", "#cancel"]:
        box = browser_page.locator(selector).bounding_box()
        assert box is not None and box["y"] + box["height"] <= 360
    assert server.exchange_payloads[0]["login_device"] == "desktop"


def _paste_viewer(page: Page, url: str, clipboard_script: str) -> None:
    page.add_init_script(clipboard_script)
    page.goto(url)
    page.wait_for_function("!document.getElementById('paste').disabled")


def _literal_keys(page: Page, instance: int = 0) -> list[int]:
    return page.evaluate(
        "i => window.__rfbInstances[i].keys.filter(k => k.length === 1).map(k => k[0])",
        instance,
    )


@pytest.mark.parametrize("shortcut", ["Control+v", "Meta+v"])
def test_paste_shortcut_preserves_printable_ascii_once_and_releases_modifiers(
    viewer_server: tuple[_ViewerServer, str], desktop_page: Page, shortcut: str
) -> None:
    server, url = viewer_server
    text = " " + "".join(chr(point) for point in range(32, 127)) + " "
    _paste_viewer(
        desktop_page,
        url,
        "window.__reads=0; Object.defineProperty(navigator,'clipboard',{value:{"
        f"readText:async()=>{{window.__reads++;return {json.dumps(text)};}}}}}});",
    )
    desktop_page.locator("#screen").evaluate("node=>{node.tabIndex=0;node.focus()}")
    desktop_page.keyboard.press(shortcut)
    desktop_page.wait_for_function("window.__rfbInstances[0].focuses === 1")
    assert _literal_keys(desktop_page) == [ord(char) for char in text]
    assert desktop_page.evaluate("window.__reads") == 1
    keys = desktop_page.evaluate("window.__rfbInstances[0].keys")
    assert all(key[2] is False for key in keys[:10])
    assert desktop_page.evaluate("window.__rfbInstances[0].blurs") == 1
    assert desktop_page.locator("#paste-value").input_value() == ""
    assert server.exchanges == 1
    assert len(server.exchange_payloads[0]) == 3


@pytest.mark.parametrize(
    "value",
    [
        "line\nline",
        "tab\tfield",
        "\x00",
        "\x7f",
        "a" * 1025,
        "\ud800",
        "prefixé",
        "prefix例",
        "prefix🔐",
        "prefixe\u0301",
    ],
)
def test_paste_invalid_text_sends_nothing(
    viewer_server: tuple[_ViewerServer, str], desktop_page: Page, value: str
) -> None:
    _, url = viewer_server
    _paste_viewer(
        desktop_page,
        url,
        "Object.defineProperty(navigator,'clipboard',{value:{readText:async()=>"
        + json.dumps(value)
        + "}});",
    )
    desktop_page.locator("#paste").click()
    assert desktop_page.locator("#status").inner_text().endswith("Nothing was inserted.")
    assert desktop_page.evaluate("window.__rfbInstances[0].keys") == []


@pytest.mark.parametrize("mode", ["denied", "missing"])
def test_native_masked_fallback_requires_insert_and_clears(
    viewer_server: tuple[_ViewerServer, str], browser_page: Page, mode: str
) -> None:
    _, url = viewer_server
    clipboard = "undefined" if mode == "missing" else "{readText:async()=>{throw Error('denied')}}"
    _paste_viewer(
        browser_page, url, f"Object.defineProperty(navigator,'clipboard',{{value:{clipboard}}});"
    )
    browser_page.locator("#paste").click()
    assert browser_page.locator("#paste-panel").is_visible()
    assert browser_page.evaluate("document.activeElement.id") == "paste-value"
    # Characters typed one at a time stay in the box until Insert.
    browser_page.locator("#paste-value").type("ab")
    browser_page.wait_for_timeout(50)
    assert _literal_keys(browser_page) == []
    browser_page.locator("#paste-insert").click()
    browser_page.wait_for_function("window.__rfbInstances[0].focuses === 1")
    assert _literal_keys(browser_page) == [ord("a"), ord("b")]
    assert browser_page.locator("#paste-value").input_value() == ""
    assert browser_page.locator("#paste-panel").is_hidden()
    # A keyboard suggestion or clipboard chip arrives as one multi-character input and is
    # sent immediately without Insert.
    browser_page.locator("#paste").click()
    browser_page.locator("#paste-value").fill("  synthetic@example.test  ")
    browser_page.wait_for_function("window.__rfbInstances[0].focuses === 2")
    assert _literal_keys(browser_page)[2:] == [ord(char) for char in "  synthetic@example.test  "]
    assert browser_page.locator("#paste-value").input_value() == ""
    assert browser_page.locator("#paste-panel").is_hidden()


@pytest.mark.parametrize("ending", ["cancel", "finalizing", "disconnect", "pagehide"])
def test_delayed_clipboard_read_is_discarded_after_teardown(
    viewer_server: tuple[_ViewerServer, str], desktop_page: Page, ending: str
) -> None:
    server, url = viewer_server
    _paste_viewer(
        desktop_page,
        url,
        "window.__reads=0;Object.defineProperty(navigator,'clipboard',{value:{"
        "readText:()=>{window.__reads++;return new Promise(r=>window.__resolvePaste=r)}}});",
    )
    desktop_page.locator("#paste").click()
    desktop_page.locator("#paste").click()
    assert desktop_page.evaluate("window.__reads") == 1
    if ending == "cancel":
        desktop_page.locator("#cancel").click()
    elif ending == "finalizing":
        server.session_status = "finalizing"
        desktop_page.wait_for_function("document.getElementById('paste').disabled")
    elif ending == "disconnect":
        desktop_page.evaluate("window.__rfbInstances[0].forceDirtyDisconnect()")
        desktop_page.wait_for_function("window.__rfbInstances.length === 2")
        desktop_page.wait_for_function("!document.getElementById('paste').disabled")
    else:
        desktop_page.evaluate("window.dispatchEvent(new PageTransitionEvent('pagehide'))")
    desktop_page.evaluate("window.__resolvePaste('must never be sent')")
    desktop_page.wait_for_timeout(50)
    assert _literal_keys(desktop_page) == []
    if ending == "disconnect":
        assert _literal_keys(desktop_page, 1) == []
    assert desktop_page.locator("#paste-value").input_value() == ""


def test_chunked_paste_stops_on_disconnect_without_replay(
    viewer_server: tuple[_ViewerServer, str], desktop_page: Page
) -> None:
    _, url = viewer_server
    _paste_viewer(
        desktop_page,
        url,
        "Object.defineProperty(navigator,'clipboard',{value:{"
        "readText:async()=> 'x'.repeat(100)}});",
    )
    desktop_page.evaluate("""() => {
      const connection=window.__rfbInstances[0], send=connection.sendKey.bind(connection);
      connection.sendKey=(...args)=>{
        send(...args);
        if(args.length===1 && connection.keys.filter(k=>k.length===1).length===33)
          connection.forceDirtyDisconnect();
      };
    }""")
    desktop_page.locator("#paste").click()
    desktop_page.wait_for_function("window.__rfbInstances.length===2")
    assert _literal_keys(desktop_page) == [ord("x")] * 33
    assert _literal_keys(desktop_page, 1) == []


def test_disconnect_during_final_paste_keystroke_is_not_reported_as_success(
    viewer_server: tuple[_ViewerServer, str], desktop_page: Page
) -> None:
    _, url = viewer_server
    _paste_viewer(
        desktop_page,
        url,
        "Object.defineProperty(navigator,'clipboard',{value:{readText:async()=>'482913'}});",
    )
    desktop_page.evaluate("""() => {
      const connection=window.__rfbInstances[0], send=connection.sendKey.bind(connection);
      connection.sendKey=(...args)=>{
        send(...args);
        if(args.length===1 && connection.keys.filter(k=>k.length===1).length===6)
          connection.forceDirtyDisconnect();
      };
    }""")
    desktop_page.locator("#paste").click()
    desktop_page.wait_for_function("window.__rfbInstances.length===2")
    desktop_page.wait_for_timeout(150)
    assert _literal_keys(desktop_page) == [ord(c) for c in "482913"]
    assert _literal_keys(desktop_page, 1) == []
    assert "sent" not in desktop_page.locator("#status").text_content()
    assert desktop_page.evaluate("window.__rfbInstances[0].focuses||0") == 0
    assert desktop_page.locator("#paste-value").input_value() == ""


@pytest.mark.parametrize("host", ["482913", "null", "silent"])
def test_host_clipboard_is_tried_before_the_fallback_box(
    viewer_server: tuple[_ViewerServer, str], browser_page: Page, host: str
) -> None:
    """Telegram's Mini App clipboard read follows a denied browser read, then the box."""
    server, url = viewer_server
    server.host_clipboard = host
    _paste_viewer(
        browser_page,
        url,
        "Object.defineProperty(navigator,'clipboard',{value:{"
        "readText:async()=>{throw Error('denied')}}});",
    )
    browser_page.locator("#paste").click()
    if host == "482913":
        browser_page.wait_for_function("window.__rfbInstances[0].focuses === 1")
        assert _literal_keys(browser_page) == [ord(c) for c in "482913"]
        assert browser_page.locator("#paste-panel").is_hidden()
    else:
        browser_page.wait_for_function("!document.getElementById('paste-panel').hidden")
        assert _literal_keys(browser_page) == []
        assert browser_page.evaluate("document.activeElement.id") == "paste-value"
    assert browser_page.evaluate("window.__hostReads") == 1


def test_host_clipboard_is_skipped_when_the_host_is_too_old(
    viewer_server: tuple[_ViewerServer, str], browser_page: Page
) -> None:
    server, url = viewer_server
    server.host_clipboard = "482913"
    server.fullscreen_mode = "old"  # isVersionAtLeast() answers false
    _paste_viewer(
        browser_page,
        url,
        "Object.defineProperty(navigator,'clipboard',{value:{"
        "readText:async()=>{throw Error('denied')}}});",
    )
    browser_page.locator("#paste").click()
    browser_page.wait_for_function("!document.getElementById('paste-panel').hidden")
    assert browser_page.evaluate("window.__hostReads") == 0
    assert _literal_keys(browser_page) == []


def test_keyboard_suggestion_into_capture_is_paced_and_keeps_keyboard_open(
    viewer_server: tuple[_ViewerServer, str], browser_page: Page
) -> None:
    """A one-time-code suggestion or clipboard chip arrives as one multi-character input."""
    _, url = viewer_server
    browser_page.goto(url)
    browser_page.wait_for_function("!document.querySelector('#keyboard').disabled")
    assert browser_page.locator("#capture").get_attribute("autocomplete") == "one-time-code"
    browser_page.locator("#keyboard").click()
    assert browser_page.evaluate("document.activeElement.id") == "capture"
    browser_page.evaluate("""() => {
      const connection=window.__rfbInstances[0], send=connection.sendKey.bind(connection);
      window.__literalAt=[];
      connection.sendKey=(...args)=>{
        if(args.length===1)window.__literalAt.push(performance.now());
        send(...args);
      };
    }""")
    browser_page.keyboard.insert_text("482913")
    browser_page.wait_for_function("window.__literalAt.length===6")
    assert _literal_keys(browser_page) == [ord(c) for c in "482913"]
    gaps = browser_page.evaluate("window.__literalAt.slice(1).map((t,i)=>t-window.__literalAt[i])")
    assert min(gaps) >= 40
    assert browser_page.evaluate("document.activeElement.id") == "capture"
    assert browser_page.locator("#keyboard").get_attribute("aria-pressed") == "true"
    assert browser_page.evaluate("window.__rfbInstances[0].focuses||0") == 0
    # Ordinary single characters are still forwarded immediately afterwards.
    browser_page.keyboard.insert_text("Z")
    browser_page.wait_for_function("window.__literalAt.length===7")
    assert _literal_keys(browser_page)[-1] == ord("Z")


def test_unsupported_keyboard_suggestion_keeps_the_immediate_path(
    viewer_server: tuple[_ViewerServer, str], browser_page: Page
) -> None:
    _, url = viewer_server
    browser_page.goto(url)
    browser_page.wait_for_function("!document.querySelector('#keyboard').disabled")
    browser_page.locator("#keyboard").click()
    browser_page.keyboard.insert_text("héé")
    browser_page.wait_for_timeout(50)
    assert _literal_keys(browser_page) == [ord("h"), ord("é"), ord("é")]
    assert browser_page.evaluate("window.__rfbInstances[0].focuses||0") == 0


def test_paste_keystrokes_are_paced_for_asynchronous_focus_advance(
    viewer_server: tuple[_ViewerServer, str], desktop_page: Page
) -> None:
    """A six-box code entry moves focus after each input; keys must not arrive in a burst."""
    _, url = viewer_server
    _paste_viewer(
        desktop_page,
        url,
        "Object.defineProperty(navigator,'clipboard',{value:{readText:async()=>'482913'}});",
    )
    desktop_page.evaluate("""() => {
      const connection=window.__rfbInstances[0], send=connection.sendKey.bind(connection);
      window.__literalAt=[];
      connection.sendKey=(...args)=>{
        if(args.length===1)window.__literalAt.push(performance.now());
        send(...args);
      };
    }""")
    desktop_page.locator("#paste").click()
    desktop_page.wait_for_function("window.__literalAt.length>=1")
    # The remaining characters wait for the pacing timer instead of being sent synchronously.
    assert len(_literal_keys(desktop_page)) < 6
    desktop_page.wait_for_function("window.__literalAt.length===6")
    assert _literal_keys(desktop_page) == [ord(c) for c in "482913"]
    gaps = desktop_page.evaluate("window.__literalAt.slice(1).map((t,i)=>t-window.__literalAt[i])")
    assert min(gaps) >= 40
    assert desktop_page.locator("#paste-value").input_value() == ""


@pytest.mark.parametrize(
    "text,valid", [("  test@example.test  ", True), ("first\nsecond", False), ("prefixé", False)]
)
def test_browser_native_paste_into_fallback_preserves_raw_validation(
    viewer_server: tuple[_ViewerServer, str], desktop_page: Page, text: str, valid: bool
) -> None:
    """Browser-generated paste event with synthetic clipboard, not a physical OS test."""
    _, url = viewer_server
    desktop_page.context.grant_permissions(["clipboard-read", "clipboard-write"])
    desktop_page.goto(url)
    desktop_page.wait_for_function("!document.getElementById('paste').disabled")
    desktop_page.evaluate("text=>navigator.clipboard.writeText(text)", text)
    # Preserve native Clipboard API write/browser paste, deny only viewer readText.
    desktop_page.evaluate("() => {navigator.clipboard.readText=async()=>{throw Error('denied')}}")
    desktop_page.locator("#paste").click()
    desktop_page.locator("#paste-value").press("ControlOrMeta+v")
    if valid:
        # A native paste into the box is sent immediately; no Insert step.
        desktop_page.wait_for_function("window.__rfbInstances[0].focuses === 1")
        assert _literal_keys(desktop_page) == [ord(char) for char in text]
        assert desktop_page.locator("#paste-value").input_value() == ""
        assert desktop_page.locator("#paste-panel").is_hidden()
    else:
        desktop_page.wait_for_function(
            "document.getElementById('status').textContent.includes('Nothing was inserted')"
        )
        assert desktop_page.locator("#paste-value").input_value() == ""
        assert desktop_page.evaluate("window.__rfbInstances[0].keys") == []


def test_pending_paste_blocks_field_changes_and_untrusted_paste(
    viewer_server: tuple[_ViewerServer, str], desktop_page: Page
) -> None:
    _, url = viewer_server
    _paste_viewer(
        desktop_page,
        url,
        "Object.defineProperty(navigator,'clipboard',{value:{"
        "readText:()=>new Promise(r=>window.__resolvePaste=r)}});",
    )
    desktop_page.locator("#screen").evaluate("""node=>{
      node.tabIndex=0;
      window.__pointerDelivered=0;window.__keysDelivered=0;window.__keyups=0;
      node.addEventListener('pointerdown',()=>window.__pointerDelivered++);
      node.addEventListener('keydown',()=>window.__keysDelivered++);
      node.addEventListener('keyup',()=>window.__keyups++);
      const data=new DataTransfer();data.setData('text/plain','untrusted');
      node.dispatchEvent(new ClipboardEvent('paste',{bubbles:true,clipboardData:data}));
    }""")
    assert _literal_keys(desktop_page) == []
    desktop_page.locator("#paste").click()
    desktop_page.locator("#next").click()
    desktop_page.locator("#enter").click()
    desktop_page.locator("#screen").focus()
    desktop_page.keyboard.press("Tab")
    desktop_page.locator("#screen").dispatch_event("pointerdown")
    assert desktop_page.evaluate("window.__pointerDelivered") == 0
    assert desktop_page.evaluate("window.__keysDelivered") == 0
    assert desktop_page.evaluate("window.__keyups") == 1
    assert desktop_page.evaluate("window.__rfbInstances[0].keys") == []
    desktop_page.evaluate("window.__resolvePaste('once')")
    desktop_page.wait_for_function("window.__rfbInstances[0].focuses === 1")
    assert _literal_keys(desktop_page) == [ord(char) for char in "once"]


def test_repeated_paste_preserves_fallback_buffer_until_explicit_insert(
    viewer_server: tuple[_ViewerServer, str], browser_page: Page
) -> None:
    _, url = viewer_server
    _paste_viewer(
        browser_page,
        url,
        "window.__reads=0;Object.defineProperty(navigator,'clipboard',{value:{"
        "readText:async()=>{window.__reads++;throw Error('denied')}}});",
    )
    browser_page.locator("#paste").click()
    browser_page.locator("#paste-value").type("ab")
    browser_page.locator("#paste").click()
    browser_page.locator("#paste").click()
    assert browser_page.evaluate("window.__reads") == 1
    assert browser_page.locator("#paste-value").input_value() == "ab"
    assert browser_page.locator("#paste-value").evaluate("node=>node===document.activeElement")
    assert browser_page.evaluate("window.__rfbInstances[0].keys") == []
    browser_page.locator("#paste-insert").click()
    browser_page.wait_for_function("window.__rfbInstances[0].focuses === 1")
    assert _literal_keys(browser_page) == [ord("a"), ord("b")]
    assert browser_page.evaluate("window.__reads") == 1
    assert browser_page.locator("#paste-value").input_value() == ""
    assert browser_page.locator("#paste-panel").is_hidden()
