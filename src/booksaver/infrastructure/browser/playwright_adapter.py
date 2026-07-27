from __future__ import annotations

import json
import logging
import re
from typing import Any

from booksaver.application.ports import PageContent, PageSnapshot
from booksaver.domain.agent import AgentAction, AgentActionType, ElementInfo, Observation
from booksaver.domain.mobile_web import MobileWebSettings

logger = logging.getLogger(__name__)

_SIGN_IN_MARKERS = re.compile(
    r"(sign in to manage|log in to your account|create an account|sign in or register)",
    re.I,
)
_SIGNED_IN_MARKERS = re.compile(
    r"(Genius\s+(?:Level|discount|deal|rate)|Bookings\s*(?:&|and)\s*Trips|"
    r"Manage account|My account|Sign out)",
    re.I,
)
_SIGNED_IN_SELECTORS = (
    '[data-testid="header-profile"]',
    '[data-testid="header-profile-menu"]',
    '[data-testid="header-bookings-link"]',
    'a[href*="myreservations"]',
)

_PAGE_TIMEOUT_MS = 45_000
_ACTION_TIMEOUT_MS = 15_000
_INVENTORY_STABLE_MS = 750
_INVENTORY_READY_SCRIPT = """
() => {
  const body = document.body;
  if (!body) return false;

  const text = body.innerText || "";
  const signedOut = /sign in to manage|log in to your account|sign in or register/i.test(text);
  const cardCount = document.querySelectorAll(
    '[data-testid="reservation-card"], [data-testid="booking-card"]'
  ).length;
  const tabCount = document.querySelectorAll('[role="tab"]').length;
  const tripCount = document.querySelectorAll('a[href*="trip_id"]').length;
  const confirmationCount = document.querySelectorAll(
    'a[href*="confirmation"], [data-testid="ReservationStatus"]'
  ).length;
  const empty = document.querySelector(
    '[data-testid="bookings-empty-state"], [data-testid="reservation-empty-state"]'
  );
  const explicitComplete = document.querySelector(
    '[data-inventory-complete="true"], [data-inventory-scopes]'
  );
  const structured = Array.from(document.querySelectorAll(
    'script[type="application/ld+json"], script[type="application/json"]'
  )).some((node) =>
    /reservationId|reservationNumber|confirmationNumber|bookingId/.test(
      node.textContent || ""
    )
  );
  const loading = document.querySelector(
    '[aria-busy="true"], [data-testid*="skeleton"], [data-testid*="loading"]'
  );
  if (loading || !(
    signedOut || cardCount || tabCount || tripCount || confirmationCount ||
    empty || explicitComplete || structured
  )) {
    delete window.__booksaverInventoryReady;
    return false;
  }

  const fingerprint = [
    cardCount, tabCount, tripCount, confirmationCount, text.length,
    structured, Boolean(empty)
  ].join(":");
  const now = Date.now();
  const previous = window.__booksaverInventoryReady;
  if (previous && previous.fingerprint === fingerprint) {
    return now - previous.observedAt >= __STABLE_MS__;
  }
  window.__booksaverInventoryReady = {fingerprint, observedAt: now};
  return false;
}
""".replace("__STABLE_MS__", str(_INVENTORY_STABLE_MS))
# Include Booking.com calendar day cells (role=checkbox + data-date) so the agent
# can click check-in/out dates — they are not <button>s.
_INTERACTIVE_SELECTOR = (
    "a, button, input, select, textarea, [role='button'], "
    "[role='checkbox'][data-date], [data-date][role='checkbox']"
)
_MAX_ELEMENTS = 120
_OBSERVATION_TEXT_CHARS = 30_000


def has_authenticated_account_context(page: Any, text: str) -> bool:
    """Require positive rendered account evidence; absence of a login CTA is insufficient."""
    if _SIGN_IN_MARKERS.search(text):
        return False
    if _SIGNED_IN_MARKERS.search(text):
        return True
    for selector in _SIGNED_IN_SELECTORS:
        try:
            locator = page.locator(selector)
            for index in range(locator.count()):
                if locator.nth(index).is_visible():
                    return True
        except Exception:
            continue
    return False


def new_mobile_context(
    browser: Any,
    settings: MobileWebSettings,
    device_descriptor: dict[str, Any],
) -> Any:
    """Create a fresh, version-matched mobile context without session fallback."""
    return browser.new_context(**settings.context_options(device_descriptor))


def _is_account_inventory_url(url: str) -> bool:
    lowered = url.lower()
    return "booking.com" in lowered and any(
        marker in lowered
        for marker in ("myreservations", "mytrips", "/confirmation")
    )


def _wait_for_account_inventory(page: Any) -> None:
    """Wait for a stable rendered inventory signal, not only initial HTML."""
    try:
        page.wait_for_load_state("networkidle", timeout=_ACTION_TIMEOUT_MS)
    except Exception:
        # Booking.com may keep background requests open. The stable DOM signal
        # below is the authoritative bounded readiness condition.
        pass
    page.wait_for_function(
        _INVENTORY_READY_SCRIPT,
        polling=250,
        timeout=_ACTION_TIMEOUT_MS,
    )


class PlaywrightBrowserSession:
    """BrowserSession adapter over Playwright's sync API (ADR-007/008).

    Playwright is imported lazily so the rest of the application (and its tests)
    work without the package installed; only actually opening a browser needs it.
    """

    def __init__(
        self,
        headless: bool = True,
        mobile_settings: MobileWebSettings | None = None,
    ) -> None:
        self._headless = headless
        self._mobile_settings = mobile_settings or MobileWebSettings()
        self._playwright: Any = None
        self._browser: Any = None
        self._context: Any = None
        self._authenticated = False

    def _ensure_context(self) -> Any:
        if self._context is not None:
            return self._context
        from playwright.sync_api import sync_playwright

        self._playwright = sync_playwright().start()
        self._browser = self._playwright.chromium.launch(headless=self._headless)
        descriptor = self._playwright.devices[
            self._mobile_settings.profile.playwright_device_name
        ]
        self._context = new_mobile_context(
            self._browser, self._mobile_settings, descriptor
        )
        return self._context

    def open_page(self, url: str) -> PageContent:
        context = self._ensure_context()
        page = context.new_page()
        try:
            page.goto(url, timeout=_PAGE_TIMEOUT_MS, wait_until="domcontentloaded")
            page.wait_for_load_state("networkidle", timeout=_PAGE_TIMEOUT_MS)
            html = page.content()
            text = page.inner_text("body")
            self._authenticated = has_authenticated_account_context(page, text)
            return PageContent(url=page.url, html=html, text=text)
        finally:
            page.close()

    def get_cookies(self) -> bytes:
        context = self._ensure_context()
        return json.dumps(context.cookies()).encode("utf-8")

    def restore_cookies(self, data: bytes) -> None:
        context = self._ensure_context()
        cookies = json.loads(data.decode("utf-8"))
        context.add_cookies(cookies)

    def is_authenticated(self) -> bool:
        return self._authenticated

    def close(self) -> None:
        if self._context is not None:
            self._context.close()
            self._context = None
        if self._browser is not None:
            self._browser.close()
            self._browser = None
        if self._playwright is not None:
            self._playwright.stop()
            self._playwright = None

    def __enter__(self) -> PlaywrightBrowserSession:
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()


class PlaywrightInteractiveBrowser:
    """InteractiveBrowser adapter for the search journey (ADR-013).

    Unlike PlaywrightBrowserSession's page-per-call model, the journey needs one
    persistent page whose state accumulates across steps.
    """

    def __init__(
        self,
        headless: bool = True,
        mobile_settings: MobileWebSettings | None = None,
    ) -> None:
        self._headless = headless
        self._mobile_settings = mobile_settings or MobileWebSettings()
        self._playwright: Any = None
        self._browser: Any = None
        self._context: Any = None
        self._page: Any = None

    def _ensure_page(self) -> Any:
        if self._page is not None:
            return self._page
        from playwright.sync_api import sync_playwright

        self._playwright = sync_playwright().start()
        self._browser = self._playwright.chromium.launch(headless=self._headless)
        descriptor = self._playwright.devices[
            self._mobile_settings.profile.playwright_device_name
        ]
        self._context = new_mobile_context(
            self._browser, self._mobile_settings, descriptor
        )
        self._page = self._context.new_page()
        self._page.set_default_timeout(_ACTION_TIMEOUT_MS)
        return self._page

    def goto(self, url: str) -> None:
        page = self._ensure_page()
        page.goto(url, timeout=_PAGE_TIMEOUT_MS, wait_until="domcontentloaded")

    def open_page(self, url: str) -> PageContent:
        """Navigate the persistent context and return bounded extraction input.

        Account synchronization uses this read-only surface so it can share the
        same caller-scoped browser lease as price checks without exposing raw
        Playwright handles to the application layer.
        """
        page = self._ensure_page()
        page.goto(url, timeout=_PAGE_TIMEOUT_MS, wait_until="domcontentloaded")
        if _is_account_inventory_url(url) or _is_account_inventory_url(page.url):
            _wait_for_account_inventory(page)
        html = page.content()
        text = page.inner_text("body")
        return PageContent(url=page.url, html=html, text=text)

    def open_inventory_scope(self, scope: str) -> PageContent:
        """Select one Booking.com inventory tab and snapshot its stable result."""
        patterns = {
            "upcoming": re.compile(r"^(active|upcoming)$", re.I),
            "past": re.compile(r"^past$", re.I),
            "cancelled": re.compile(r"^(canceled|cancelled)$", re.I),
        }
        try:
            pattern = patterns[scope]
        except KeyError as exc:
            raise ValueError(f"Unsupported Booking.com inventory scope: {scope}") from exc
        page = self._ensure_page()
        tab = page.get_by_role("tab", name=pattern).first
        tab.click(timeout=_ACTION_TIMEOUT_MS)
        page.evaluate("delete window.__booksaverInventoryReady")
        _wait_for_account_inventory(page)
        return PageContent(
            url=page.url,
            html=page.content(),
            text=page.inner_text("body"),
        )

    def click(self, selector: str) -> None:
        self._ensure_page().locator(selector).first.click()

    def click_first_visible(self, selector: str) -> None:
        page = self._ensure_page()
        locator = page.locator(selector)
        for i in range(locator.count()):
            item = locator.nth(i)
            if item.is_visible():
                item.click(timeout=_ACTION_TIMEOUT_MS)
                return
        if locator.count() > 0:
            locator.first.click(force=True, timeout=_ACTION_TIMEOUT_MS)
            return
        raise RuntimeError(f"No visible element matching: {selector}")

    def fill(self, selector: str, text: str) -> None:
        self._ensure_page().locator(selector).first.fill(text)

    def press(self, selector: str, key: str) -> None:
        self._ensure_page().locator(selector).first.press(key)

    def wait_for(self, selector: str, timeout_ms: int | None = None) -> None:
        self._ensure_page().locator(selector).first.wait_for(
            state="visible", timeout=timeout_ms or _ACTION_TIMEOUT_MS
        )

    def exists(self, selector: str) -> bool:
        count: int = self._ensure_page().locator(selector).count()
        return count > 0

    def query_text(self, selector: str) -> list[str]:
        page = self._ensure_page()
        locator = page.locator(selector)
        texts: list[str] = []
        for i in range(locator.count()):
            element = locator.nth(i)
            value = element.input_value() if element.evaluate(
                "el => el.tagName === 'INPUT' || el.tagName === 'TEXTAREA'"
            ) else element.inner_text()
            texts.append(value.strip())
        return texts

    def query_attr(self, selector: str, attr: str) -> list[str]:
        page = self._ensure_page()
        locator = page.locator(selector)
        values: list[str] = []
        for i in range(locator.count()):
            raw = locator.nth(i).get_attribute(attr)
            if raw is not None:
                values.append(raw)
        return values

    def snapshot(self) -> PageSnapshot:
        page = self._ensure_page()
        return PageSnapshot(url=page.url, title=page.title(), text=page.inner_text("body"))

    # ── agent surface (bolt 007, ADR-015/016) ────────────────────────────────

    def observe(self) -> Observation:
        """Tier-1 observation: URL, title, bounded text, and enumerated visible
        interactive elements. Refs are valid until the next observe()."""
        page = self._ensure_page()
        locator = page.locator(_INTERACTIVE_SELECTOR)
        elements: list[ElementInfo] = []
        self._ref_map: dict[str, Any] = {}
        count = min(locator.count(), _MAX_ELEMENTS * 3)  # scan cap before visibility filter
        for i in range(count):
            if len(elements) >= _MAX_ELEMENTS:
                break
            handle = locator.nth(i)
            try:
                if not handle.is_visible():
                    continue
                tag = handle.evaluate("el => el.tagName.toLowerCase()")
                role_attr = handle.get_attribute("role") or ""
                if role_attr == "checkbox":
                    role = "checkbox"
                else:
                    role = {"a": "link", "input": "input", "select": "select",
                            "textarea": "input"}.get(tag, "button")
                label = (
                    handle.get_attribute("aria-label")
                    or handle.inner_text()
                    or handle.get_attribute("placeholder")
                    or ""
                ).strip()[:120]
                if not label and handle.get_attribute("data-date"):
                    label = f"date {handle.get_attribute('data-date')}"
                href = handle.get_attribute("href") if role == "link" else None
            except Exception:
                continue
            ref = f"e{len(elements)}"
            self._ref_map[ref] = handle
            elements.append(ElementInfo(ref=ref, role=role, label=label, href=href))
        return Observation(
            url=page.url,
            title=page.title(),
            text=page.inner_text("body")[:_OBSERVATION_TEXT_CHARS],
            elements=tuple(elements),
        )

    def act(self, action: AgentAction) -> None:
        """Dispatch a bounded agent action (ADR-016). Unknown/stale refs raise."""
        page = self._ensure_page()
        if action.type is AgentActionType.SCROLL:
            delta = -600 if (action.value or "").lower() == "up" else 600
            page.mouse.wheel(0, delta)
            return
        handle = getattr(self, "_ref_map", {}).get(action.ref or "")
        if handle is None:
            raise RuntimeError(f"Unknown or stale element ref: {action.ref!r}")
        if action.type is AgentActionType.CLICK:
            handle.click()
        elif action.type is AgentActionType.FILL:
            handle.fill(action.value or "")
        elif action.type is AgentActionType.SELECT:
            handle.select_option(action.value or "")
        else:
            raise RuntimeError(f"Action {action.type.value} is not a browser action")

    def screenshot(self) -> bytes:
        result: bytes = self._ensure_page().screenshot(type="png")
        return result

    def get_cookies(self) -> bytes:
        self._ensure_page()
        return json.dumps(self._context.cookies()).encode("utf-8")

    def restore_cookies(self, data: bytes) -> None:
        self._ensure_page()
        self._context.add_cookies(json.loads(data.decode("utf-8")))

    def is_authenticated(self) -> bool:
        try:
            page = self._ensure_page()
            return has_authenticated_account_context(
                page, page.inner_text("body")
            )
        except Exception:
            return False

    def close(self) -> None:
        for attr in ("_page", "_context", "_browser"):
            obj = getattr(self, attr)
            if obj is not None:
                try:
                    obj.close()
                except Exception:
                    pass
                setattr(self, attr, None)
        if self._playwright is not None:
            self._playwright.stop()
            self._playwright = None

    def __enter__(self) -> PlaywrightInteractiveBrowser:
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()


def interactive_login(login_url: str = "https://account.booking.com/sign-in") -> bytes:
    """Open a headed browser for manual login; return cookies once the user finishes.

    Blocks until the user closes the browser window (or 10 minutes pass).
    """
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()
        page.goto(login_url)
        print("A browser window has opened. Log in to Booking.com, then close the window.")
        try:
            page.wait_for_event("close", timeout=600_000)
        except Exception:
            logger.info("Login window wait ended (timeout or navigation); capturing cookies")
        cookies = json.dumps(context.cookies()).encode("utf-8")
        browser.close()
        return cookies
