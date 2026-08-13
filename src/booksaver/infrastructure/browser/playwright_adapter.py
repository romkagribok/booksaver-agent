from __future__ import annotations

import json
import logging
import re
from datetime import UTC, datetime
from typing import Any
from urllib.parse import parse_qs, urljoin, urlsplit, urlunsplit
from uuid import uuid4

from booksaver.application.browser_resilience import DOM_STEP_REGISTRY
from booksaver.application.ports import PageContent, PageSnapshot
from booksaver.domain.agent import (
    AgentAction,
    AgentActionType,
    ElementInfo,
    Observation,
    blocked_url_reason,
)
from booksaver.domain.browser_resilience import (
    DomCapability,
    DomStepId,
    PageState,
    PopupAdoptionReceipt,
    PopupAdoptionResult,
    PopupRefusalReason,
)
from booksaver.domain.mobile_web import MobileWebSettings
from booksaver.infrastructure.browser.page_state import (
    assess_page_state,
    assessment_is_protected,
    assessment_proves_authenticated,
)

logger = logging.getLogger(__name__)

# Structural coverage declaration for the production session-validation seam.
# Keep this domain-only tuple next to the workflow that owns the DOM dependency;
# tests compose workflow declarations and compare them with the central policy.
DOM_STEPS: tuple[DomStepId, ...] = (DomStepId.SESSION_VALIDATION,)

_PAGE_TIMEOUT_MS = 45_000
_ACTION_TIMEOUT_MS = 15_000
_ACCOUNT_VERIFICATION_URL = "https://secure.booking.com/myreservations.html"
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
_MAX_POPUP_URLS = 16
_MAX_PAGE_METADATA_CHARS = 512
_MAX_SCROLL_Y = 2_147_483_647
_OPAQUE_PATH_SEGMENT = re.compile(
    r"^(?:\d{8,}|[0-9a-f]{8}-[0-9a-f-]{20,}|[A-Za-z0-9_-]{16,})$",
    re.I,
)


def has_authenticated_account_context(page: Any, text: str) -> bool:
    """Require fresh strong supported-page proof, never weak account chrome."""
    return assessment_proves_authenticated(assess_page_state(page, text))


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


def _sanitize_top_level_url(raw_url: str) -> str:
    """Return bounded destination metadata without credentials or URL state.

    Observed destinations are safety evidence for the recovery controller, not
    navigation sources. Host and route shape remain inspectable while userinfo,
    query strings, fragments, confirmation identifiers, and other opaque path
    values never reach the provider observation.
    """
    try:
        parsed = urlsplit(raw_url)
    except ValueError:
        return "unavailable:invalid-url"

    scheme = parsed.scheme.lower()
    if scheme not in {"http", "https"}:
        if scheme == "about" and parsed.path == "blank":
            return "about:blank"
        return f"{scheme or 'unavailable'}:"

    hostname = (parsed.hostname or "").lower()
    if not hostname:
        return "unavailable:missing-host"
    netloc = f"[{hostname}]" if ":" in hostname else hostname
    path_segments: list[str] = []
    redact_next_segment = False
    for segment in (parsed.path or "/").split("/"):
        lowered = segment.lower()
        sensitive = redact_next_segment or bool(_OPAQUE_PATH_SEGMENT.fullmatch(segment))
        path_segments.append("{id}" if segment and sensitive else segment)
        redact_next_segment = any(
            marker in lowered
            for marker in ("confirmation", "reservation", "mybooking")
        )
    path = "/".join(path_segments) or "/"
    sanitized = urlunsplit((scheme, netloc, path, "", ""))
    if len(sanitized) > _MAX_PAGE_METADATA_CHARS:
        return "unavailable:popup-url-too-long"
    return sanitized


def _agent_destination_problem(raw_url: str) -> str | None:
    """Return a non-sensitive reason the controllable page cannot be acted on."""
    sanitized = _sanitize_top_level_url(raw_url)
    parsed = urlsplit(sanitized)
    hostname = (parsed.hostname or "").casefold()
    if parsed.scheme != "https" or not (
        hostname == "booking.com" or hostname.endswith(".booking.com")
    ):
        return "controllable page is not a secure Booking.com destination"
    if blocked_url_reason(sanitized) is not None:
        return "controllable page is a reservation-mutating destination"
    return None


def _popup_destination_refusal(
    step_id: DomStepId, raw_url: str
) -> PopupRefusalReason | None:
    """Validate a raw child destination against the code-selected step."""
    try:
        parsed = urlsplit(raw_url)
    except ValueError:
        return PopupRefusalReason.OBSERVATION_UNAVAILABLE
    hostname = (parsed.hostname or "").casefold().rstrip(".")
    if parsed.scheme.casefold() != "https" or not (
        hostname == "booking.com" or hostname.endswith(".booking.com")
    ):
        return PopupRefusalReason.EXTERNAL_ORIGIN
    if blocked_url_reason(raw_url) is not None:
        return PopupRefusalReason.MUTATING_DESTINATION

    path = parsed.path.casefold()
    if step_id is DomStepId.PRICE_PROPERTY_OPEN:
        return (
            None
            if path.startswith("/hotel/")
            else PopupRefusalReason.UNSUPPORTED_ROUTE
        )
    if step_id is DomStepId.INVENTORY_DETAIL:
        is_detail = path.startswith("/confirmation") or "trip_id" in parse_qs(
            parsed.query
        )
        return None if is_detail else PopupRefusalReason.UNSUPPORTED_ROUTE
    return PopupRefusalReason.IRRELEVANT_TO_STEP


def _popup_assessment_refusal(state: PageState) -> PopupRefusalReason | None:
    if state is PageState.OBSERVATION_UNAVAILABLE:
        return PopupRefusalReason.OBSERVATION_UNAVAILABLE
    if state is PageState.EXTERNAL:
        return PopupRefusalReason.EXTERNAL_ORIGIN
    if state is PageState.PROHIBITED:
        return PopupRefusalReason.MUTATING_DESTINATION
    if state in {
        PageState.AUTHENTICATION_REQUIRED,
        PageState.MFA_REQUIRED,
        PageState.CAPTCHA,
        PageState.BOT_WALL,
    }:
        return PopupRefusalReason.PROTECTED_DESTINATION
    return None


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
            assessment = assess_page_state(page, text)
            self._authenticated = assessment_proves_authenticated(assessment)
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
        self._authenticated_verified = False
        self._last_action_pages: tuple[Any, ...] | None = None

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
        self._record_page_assessment(page, text)
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
        text = page.inner_text("body")
        self._record_page_assessment(page, text)
        return PageContent(
            url=page.url,
            html=page.content(),
            text=text,
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
        interactive elements. Refs are valid until the next observe().

        Top-level popup metadata is intentionally observational only. The
        controllable page remains ``self._page``; recovery may diagnose a popup
        or fail closed on its destination, but this adapter never adopts it.
        """
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
                raw_href = handle.get_attribute("href") if role == "link" else None
                href = (
                    _sanitize_top_level_url(urljoin(str(page.url), raw_href))
                    if raw_href
                    else None
                )
            except Exception:
                continue
            ref = f"e{len(elements)}"
            self._ref_map[ref] = handle
            elements.append(ElementInfo(ref=ref, role=role, label=label, href=href))
        popup_count, popup_urls = self._popup_metadata(page)
        return Observation(
            url=_sanitize_top_level_url(str(page.url)),
            title=page.title(),
            text=page.inner_text("body")[:_OBSERVATION_TEXT_CHARS],
            elements=tuple(elements),
            popup_count=popup_count,
            popup_urls=popup_urls,
            scroll_y=self._scroll_y(page),
        )

    def _popup_metadata(self, controllable_page: Any) -> tuple[int, tuple[str, ...]]:
        context = self._context
        if context is None:
            return 0, ()
        try:
            popup_pages = [page for page in context.pages if page is not controllable_page]
        except Exception:
            return 0, ()

        popup_count = len(popup_pages)
        if popup_count > _MAX_POPUP_URLS:
            inspected_pages = popup_pages[: _MAX_POPUP_URLS - 1]
        else:
            inspected_pages = popup_pages
        urls: list[str] = []
        for popup in inspected_pages:
            try:
                urls.append(_sanitize_top_level_url(str(popup.url)))
            except Exception:
                urls.append("unavailable:popup-url")
        if popup_count > _MAX_POPUP_URLS:
            # The explicit marker lets the controller fail closed without
            # rendering an attacker-controlled, unbounded number of URLs.
            urls.append("unavailable:popup-metadata-overflow")
        return popup_count, tuple(urls)

    @staticmethod
    def _scroll_y(page: Any) -> int:
        try:
            raw = page.evaluate(
                "() => Math.round(window.scrollY || window.pageYOffset || 0)"
            )
            return max(0, min(int(raw), _MAX_SCROLL_Y))
        except (TypeError, ValueError, OverflowError):
            return 0
        except Exception:
            return 0

    def act(self, action: AgentAction) -> None:
        """Dispatch a bounded agent action (ADR-016). Unknown/stale refs raise."""
        page = self._ensure_page()
        destination_problem = _agent_destination_problem(str(page.url))
        if destination_problem is not None:
            raise RuntimeError(f"Agent action refused: {destination_problem}")
        if action.type is AgentActionType.SCROLL:
            delta = -600 if (action.value or "").lower() == "up" else 600
            page.mouse.wheel(0, delta)
            return
        handle = getattr(self, "_ref_map", {}).get(action.ref or "")
        if handle is None:
            raise RuntimeError(f"Unknown or stale element ref: {action.ref!r}")
        self._last_action_pages = self._current_pages()
        if action.type is AgentActionType.CLICK:
            handle.click()
        elif action.type is AgentActionType.FILL:
            handle.fill(action.value or "")
        elif action.type is AgentActionType.SELECT:
            handle.select_option(action.value or "")
        else:
            raise RuntimeError(f"Action {action.type.value} is not a browser action")

    def adopt_read_only_popup(self, step_id: DomStepId) -> PopupAdoptionResult:
        """Adopt one safe popup created by the immediately preceding action.

        Page identity and route selection remain entirely adapter-owned.  The
        model supplies neither the child page nor a URL; its guarded click only
        creates browser evidence that this method can accept or refuse.
        """
        definition = DOM_STEP_REGISTRY.definition(step_id)
        if (
            DomCapability.ADOPT_APPROVED_READ_ONLY_POPUP
            not in definition.safe_capabilities
        ):
            return self._popup_refusal(PopupRefusalReason.IRRELEVANT_TO_STEP)

        baseline = self._last_action_pages
        current = self._current_pages()
        if baseline is None or current is None:
            return self._popup_refusal(PopupRefusalReason.OBSERVATION_UNAVAILABLE)
        if self._page not in baseline or any(page is not self._page for page in baseline):
            return self._popup_refusal(PopupRefusalReason.MULTIPLE_OPENED)

        new_pages = [
            page for page in current if not any(page is prior for prior in baseline)
        ]
        if not new_pages:
            return self._popup_refusal(PopupRefusalReason.NONE_OPENED)
        if len(new_pages) != 1:
            return self._popup_refusal(
                PopupRefusalReason.MULTIPLE_OPENED, close_pages=new_pages
            )

        popup = new_pages[0]
        try:
            wait = getattr(popup, "wait_for_load_state", None)
            if callable(wait):
                wait("domcontentloaded", timeout=_ACTION_TIMEOUT_MS)
            raw_url = str(popup.url)
        except Exception:
            return self._popup_refusal(
                PopupRefusalReason.OBSERVATION_UNAVAILABLE, close_pages=(popup,)
            )

        destination_refusal = _popup_destination_refusal(step_id, raw_url)
        if destination_refusal is not None:
            return self._popup_refusal(destination_refusal, close_pages=(popup,))

        try:
            text = popup.inner_text("body")
            assessment = assess_page_state(popup, text)
        except Exception:
            return self._popup_refusal(
                PopupRefusalReason.OBSERVATION_UNAVAILABLE, close_pages=(popup,)
            )
        protected_refusal = _popup_assessment_refusal(assessment.state)
        if protected_refusal is not None:
            return self._popup_refusal(protected_refusal, close_pages=(popup,))

        previous = self._page
        try:
            popup.set_default_timeout(_ACTION_TIMEOUT_MS)
            previous.close()
        except Exception:
            return self._popup_refusal(
                PopupRefusalReason.OBSERVATION_UNAVAILABLE, close_pages=(popup,)
            )

        self._page = popup
        self._last_action_pages = None
        self._authenticated_verified = False
        return PopupAdoptionResult(
            receipt=PopupAdoptionReceipt(
                step_id=step_id,
                observation_id=f"popup-{uuid4().hex}",
                page_id=f"page-{uuid4().hex}",
                adopted_at=datetime.now(UTC),
            )
        )

    def _current_pages(self) -> tuple[Any, ...] | None:
        if self._context is None:
            return None
        try:
            return tuple(self._context.pages)
        except Exception:
            return None

    def _popup_refusal(
        self,
        reason: PopupRefusalReason,
        *,
        close_pages: tuple[Any, ...] | list[Any] = (),
    ) -> PopupAdoptionResult:
        for page in close_pages:
            try:
                page.close()
            except Exception:
                pass
        self._last_action_pages = None
        return PopupAdoptionResult(refusal_reason=reason)

    def screenshot(self) -> bytes:
        page = self._ensure_page()
        destination_problem = _agent_destination_problem(str(page.url))
        if destination_problem is not None:
            raise RuntimeError(f"Agent screenshot refused: {destination_problem}")
        result: bytes = page.screenshot(type="png")
        return result

    def get_cookies(self) -> bytes:
        self._ensure_page()
        return json.dumps(self._context.cookies()).encode("utf-8")

    def restore_cookies(self, data: bytes) -> None:
        self._ensure_page()
        self._context.add_cookies(json.loads(data.decode("utf-8")))
        self._authenticated_verified = False
        self._last_action_pages = None

    def verify_authenticated_account(self) -> bool:
        """Run one fixed read-only account probe and retain only code proof."""
        try:
            page = self._ensure_page()
            page.goto(
                _ACCOUNT_VERIFICATION_URL,
                timeout=_PAGE_TIMEOUT_MS,
                wait_until="domcontentloaded",
            )
            _wait_for_account_inventory(page)
            self._record_page_assessment(page, page.inner_text("body"))
            return self._authenticated_verified
        except Exception:
            self._authenticated_verified = False
            return False

    def is_authenticated(self) -> bool:
        try:
            page = self._ensure_page()
            self._record_page_assessment(page, page.inner_text("body"))
            return self._authenticated_verified
        except Exception:
            return False

    def _record_page_assessment(self, page: Any, text: str) -> None:
        assessment = assess_page_state(page, text)
        if assessment_is_protected(assessment):
            self._authenticated_verified = False
        elif assessment_proves_authenticated(assessment):
            self._authenticated_verified = True

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
        self._authenticated_verified = False
        self._last_action_pages = None

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
