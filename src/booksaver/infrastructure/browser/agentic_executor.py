"""Local Stagehand price executor with one guarded Anthropic computer-use fallback.

Third-party browser and model objects are deliberately contained here.  Public requests/results
use only BookSaver's provider-neutral contracts, and cookie bytes enter through a code-owned CDP
bootstrap before Stagehand is attached.
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import socket
import threading
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from decimal import InvalidOperation
from enum import Enum
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Protocol, TypeVar, cast
from urllib.parse import urlencode, urlsplit

from booksaver.application.async_runner import AsyncLoopRunner
from booksaver.application.browser_executor import ExecutionMeter, InMemorySessionLeaseBroker
from booksaver.application.model_policy import AdmittedModelAttempt, BrowserJobCostBudget
from booksaver.application.ports import SessionRestoreTarget
from booksaver.domain.agent import LLMUsage
from booksaver.domain.browser_executor import (
    AllInEvidence,
    EvidenceCompleteness,
    ExecutorSafetyViolation,
    ObservationSource,
    ObservedOffer,
    ObservedQueryFacts,
    PriceExecutionRequest,
    PriceExecutionResult,
    PriceExecutionStatus,
    RedactedProvenance,
    RefundabilityEvidence,
)
from booksaver.domain.browser_guard import (
    BrowserActionGuard,
    BrowserActionProposal,
    BrowserActionType,
    CoordinateHitTest,
    DestinationSnapshot,
    ExecutorEgressKind,
    GuardRejection,
    classify_executor_egress,
)
from booksaver.domain.mobile_web import MobileWebSettings
from booksaver.domain.model_policy import (
    AdaptiveModelPortfolio,
    EscalationTrigger,
    ModelAttemptOutcome,
    ModelAttemptPlan,
    ModelRole,
    TokenEnvelope,
)
from booksaver.domain.value_objects import Money, Occupancy
from booksaver.infrastructure.remote_auth.network_session import (
    ACCOUNT_PROBE_URL,
    is_authenticated_account_probe_response,
)

logger = logging.getLogger(__name__)

_STAGEHAND_MODEL = "anthropic/claude-sonnet-5"
_ANTHROPIC_MODEL = "claude-sonnet-5"
_ANTHROPIC_API_BASE = "https://api.anthropic.com"
_COMPUTER_USE_BETA = "computer-use-2025-11-24"
_VIEWPORT_WIDTH = 1280
_VIEWPORT_HEIGHT = 800
_MODEL_ENVELOPE = TokenEnvelope(30_000, 4_096)
_BOOKING_ALLOWED_DOMAINS = ["booking.com", "*.booking.com"]
_SAFE_TYPED_VALUES = frozenset(
    {
        "ArrowDown",
        "ArrowUp",
        "ArrowLeft",
        "ArrowRight",
        "PageDown",
        "PageUp",
        "Home",
        "End",
        "Escape",
        "Tab",
        "Shift+Tab",
    }
)


class SemanticFailure(Enum):
    NO_ACTION = "no_action"
    PROPOSAL_REJECTED = "proposal_rejected"
    ACTION_FAILED = "action_failed"
    EXTRACTION_INVALID = "extraction_invalid"
    DESTINATION_CHANGED = "destination_changed"
    NON_ALLOWLISTED_DESTINATION = "non_allowlisted_destination"


class BrowserNavigationFailureKind(Enum):
    REDIRECT_LOOP = "redirect_loop"
    TIMEOUT = "timeout"
    CONNECTION = "connection"
    CERTIFICATE = "certificate"
    TRANSPORT = "transport"
    UNKNOWN = "unknown"


class BrowserNavigationFailure(RuntimeError):
    """Closed, content-free failure raised before provider perception."""

    def __init__(self, kind: BrowserNavigationFailureKind) -> None:
        self.kind = kind
        super().__init__(kind.value)


class ComputerTurnKind(Enum):
    ACTION = "action"
    SUBMISSION = "submission"
    TERMINAL = "terminal"


@dataclass(frozen=True, slots=True)
class ProviderUsage:
    tokens: LLMUsage
    latency_ms: int


@dataclass(frozen=True, slots=True)
class SemanticAction:
    description: str
    method: str
    selector: str = field(repr=False)
    token: object = field(repr=False)


@dataclass(frozen=True, slots=True)
class InspectedElement:
    label: str
    role: str
    href: str | None
    visible: bool
    enabled: bool


@dataclass(frozen=True, slots=True)
class TypedObservation:
    facts: ObservedQueryFacts
    offers: tuple[ObservedOffer, ...]
    evidence_item_count: int


@dataclass(frozen=True, slots=True)
class SemanticObservationResult:
    observation: TypedObservation
    usage: ProviderUsage


@dataclass(frozen=True, slots=True)
class ComputerActionRequest:
    action: BrowserActionType
    tool_use_id: str
    x: int | None = None
    y: int | None = None
    delta_y: int = 0
    value: str | None = None
    wait_ms: int | None = None
    zoom_region: tuple[int, int, int, int] | None = None


@dataclass(frozen=True, slots=True)
class ComputerTurn:
    kind: ComputerTurnKind
    usage: ProviderUsage
    action: ComputerActionRequest | None = None
    observation: TypedObservation | None = None
    terminal_status: PriceExecutionStatus | None = None

    def __post_init__(self) -> None:
        populated = sum(
            item is not None for item in (self.action, self.observation, self.terminal_status)
        )
        if populated != 1:
            raise ValueError("computer turn must contain exactly one typed outcome")


class StagehandRuntimePort(SessionRestoreTarget, Protocol):
    async def launch(self) -> None: ...
    async def apply_session(self) -> None: ...
    async def attach(self, api_key: str) -> None: ...
    async def navigate(self, url: str) -> None: ...
    async def destination(self) -> DestinationSnapshot: ...
    async def viewport_size(self) -> tuple[int, int]: ...
    async def observe_property(
        self, property_name: str
    ) -> tuple[SemanticAction | None, ProviderUsage]: ...
    async def inspect(self, action: SemanticAction) -> InspectedElement | None: ...
    async def replay(self, action: SemanticAction) -> None: ...
    async def extract(self) -> SemanticObservationResult: ...
    async def screenshot(self) -> bytes: ...
    async def hit_test(self, x: int, y: int) -> CoordinateHitTest | None: ...
    async def focused_element(self) -> InspectedElement | None: ...
    async def execute_action(self, action: ComputerActionRequest) -> None: ...
    async def verified_session_refresh(self) -> bytes | None: ...
    async def close(self) -> None: ...


class ComputerUseModelPort(Protocol):
    def next_turn(
        self,
        *,
        screenshot: bytes,
        request: PriceExecutionRequest,
        prior_tool_use_id: str | None,
    ) -> ComputerTurn: ...


class _TelemetryHandler(BaseHTTPRequestHandler):
    def do_POST(self) -> None:  # noqa: N802 - stdlib handler hook
        length = int(self.headers.get("content-length", "0"))
        if length:
            self.rfile.read(min(length, 5_000_000))
        self.send_response(200)
        self.end_headers()

    def log_message(self, _format: str, *_args: object) -> None:
        return


class LoopbackTelemetrySink:
    """Discard Stagehand OTLP payloads locally so its external default is never used."""

    def __init__(self) -> None:
        self._server = ThreadingHTTPServer(("127.0.0.1", 0), _TelemetryHandler)
        self._thread = threading.Thread(
            target=self._server.serve_forever,
            name="booksaver-stagehand-telemetry",
            daemon=True,
        )
        self._thread.start()

    @property
    def endpoint(self) -> str:
        address = self._server.server_address
        raw_host, port = address[0], address[1]
        host = raw_host.decode("ascii") if isinstance(raw_host, bytes) else str(raw_host)
        return f"http://{host}:{port}/v1/traces"

    def close(self) -> None:
        self._server.shutdown()
        self._server.server_close()
        self._thread.join(timeout=2)


class CodeOwnedSessionBootstrap:
    """Holds opaque cookie bytes only until a code-owned Playwright CDP injection."""

    def __init__(self) -> None:
        self._material: bytes | None = None

    def restore_session(self, data: bytes) -> None:
        if self._material is not None:
            raise ValueError("session bootstrap is single use")
        self._material = bytes(data)

    async def apply(self, cdp_url: str) -> None:
        material = self._material
        self._material = None
        if material is None:
            raise ValueError("session lease was not restored")
        try:
            cookies = self._decode_cookies(material)
            from playwright.async_api import async_playwright

            playwright = await async_playwright().start()
            browser: Any | None = None
            try:
                browser = await playwright.chromium.connect_over_cdp(cdp_url)
                contexts = browser.contexts
                if len(contexts) != 1:
                    raise RuntimeError("transient browser must contain exactly one context")
                await contexts[0].add_cookies(cast(Any, cookies))
            finally:
                # Stopping Playwright disconnects its CDP client without terminating Chromium.
                await playwright.stop()
                del browser
        finally:
            material = b""

    @staticmethod
    def _decode_cookies(material: bytes) -> list[dict[str, Any]]:
        try:
            raw = json.loads(material.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError("session material is not a cookie list") from exc
        if not isinstance(raw, list) or not raw:
            raise ValueError("session material must contain cookies")
        cookies: list[dict[str, Any]] = []
        for item in raw:
            if not isinstance(item, dict):
                raise ValueError("session cookie must be an object")
            domain = item.get("domain")
            if not isinstance(domain, str):
                raise ValueError("session cookie domain is required")
            normalized = domain.lstrip(".").casefold()
            if normalized != "booking.com" and not normalized.endswith(".booking.com"):
                raise ValueError("session cookie is outside Booking.com")
            cookies.append(dict(item))
        return cookies


def _available_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


def _classify_navigation_failure(detail: str) -> BrowserNavigationFailureKind:
    normalized = detail.upper()
    if "ERR_TOO_MANY_REDIRECTS" in normalized:
        return BrowserNavigationFailureKind.REDIRECT_LOOP
    if "ERR_TIMED_OUT" in normalized or "TIMEOUT" in normalized:
        return BrowserNavigationFailureKind.TIMEOUT
    if "ERR_CERT" in normalized or "CERTIFICATE" in normalized:
        return BrowserNavigationFailureKind.CERTIFICATE
    if any(
        marker in normalized
        for marker in (
            "ERR_CONNECTION",
            "ERR_NAME_NOT_RESOLVED",
            "ERR_INTERNET_DISCONNECTED",
            "ERR_ADDRESS_UNREACHABLE",
        )
    ):
        return BrowserNavigationFailureKind.CONNECTION
    if "NET::ERR_" in normalized:
        return BrowserNavigationFailureKind.TRANSPORT
    return BrowserNavigationFailureKind.UNKNOWN


class _NavigationFailureObserver:
    """Observe only a closed main-document transport category over loopback CDP."""

    def __init__(self, playwright: Any | None = None) -> None:
        self._playwright = playwright
        self._listeners: list[tuple[Any, Callable[[Any], None]]] = []
        self.failure: BrowserNavigationFailureKind | None = None

    @classmethod
    async def open(cls, cdp_url: str | None) -> _NavigationFailureObserver:
        if cdp_url is None:
            return cls()
        from playwright.async_api import async_playwright

        playwright: Any | None = None
        try:
            playwright = await async_playwright().start()
            browser = await playwright.chromium.connect_over_cdp(cdp_url)
            observer = cls(playwright)
            for context in browser.contexts:
                for page in context.pages:
                    def on_failed(
                        request: Any,
                        *,
                        target: _NavigationFailureObserver = observer,
                    ) -> None:
                        try:
                            if not request.is_navigation_request():
                                return
                            target.failure = _classify_navigation_failure(str(request.failure))
                        except Exception:
                            target.failure = BrowserNavigationFailureKind.UNKNOWN

                    page.on("requestfailed", on_failed)
                    observer._listeners.append((page, on_failed))
            return observer
        except Exception:
            if playwright is not None:
                await playwright.stop()
            return cls()

    async def close(self) -> None:
        for page, listener in self._listeners:
            try:
                page.remove_listener("requestfailed", listener)
            except Exception:
                pass
        self._listeners.clear()
        if self._playwright is not None:
            await self._playwright.stop()
            self._playwright = None


class LocalStagehandRuntime:
    """Stagehand 4 local runtime on one transient Chromium profile."""

    def __init__(self, mobile_settings: MobileWebSettings | None = None) -> None:
        self._mobile_settings = mobile_settings or MobileWebSettings()
        self._bootstrap = CodeOwnedSessionBootstrap()
        self._browser: Any | None = None
        self._stagehand: Any | None = None
        self._page: Any | None = None
        self._cdp_url: str | None = None
        self._telemetry: LoopbackTelemetrySink | None = None
        self._next_screenshot_region: tuple[int, int, int, int] | None = None
        self._viewport_width = _VIEWPORT_WIDTH
        self._viewport_height = _VIEWPORT_HEIGHT

    def restore_session(self, data: bytes) -> None:
        self._bootstrap.restore_session(data)

    async def launch(self) -> None:
        try:
            from playwright.async_api import async_playwright
            from stagehand import local_browser
        except ImportError as exc:
            raise RuntimeError("Stagehand 4.0.1 runtime is not installed") from exc
        playwright = await async_playwright().start()
        try:
            executable_path = playwright.chromium.executable_path
            descriptor = dict(
                playwright.devices[self._mobile_settings.profile.playwright_device_name]
            )
            mobile_options = self._mobile_settings.context_options(descriptor)
        finally:
            await playwright.stop()
        viewport = cast(dict[str, int], mobile_options["viewport"])
        self._viewport_width = int(viewport["width"])
        self._viewport_height = int(viewport["height"])
        user_agent = str(mobile_options["user_agent"])
        port = _available_port()
        self._cdp_url = f"http://127.0.0.1:{port}"
        self._browser = await local_browser.launch(
            args=[f"--user-agent={user_agent}"],
            executable_path=executable_path,
            port=port,
            headless=True,
            locale=self._mobile_settings.locale,
            viewport_width=self._viewport_width,
            viewport_height=self._viewport_height,
            device_scale_factor=float(mobile_options["device_scale_factor"]),
            has_touch=mobile_options["has_touch"] is True,
            chromium_sandbox=False,
            accept_downloads=False,
            keep_alive=False,
        )

    async def apply_session(self) -> None:
        if self._cdp_url is None:
            raise RuntimeError("local browser has not launched")
        await self._bootstrap.apply(self._cdp_url)

    async def attach(self, api_key: str) -> None:
        if self._browser is None:
            raise RuntimeError("local browser has not launched")
        from stagehand import Stagehand

        self._telemetry = LoopbackTelemetrySink()
        if (
            classify_executor_egress(self._telemetry.endpoint)
            is not ExecutorEgressKind.LOOPBACK
        ):
            raise RuntimeError("Stagehand telemetry must remain on loopback")
        if (
            classify_executor_egress(_ANTHROPIC_API_BASE)
            is not ExecutorEgressKind.ANTHROPIC
        ):
            raise RuntimeError("Stagehand model endpoint is outside the executor allowlist")
        stagehand = await Stagehand.create(
            browser=self._browser,
            model=_STAGEHAND_MODEL,
            model_api_key=api_key,
            telemetry={"traces": {"endpoint": self._telemetry.endpoint}},
            self_heal=False,
            cache=False,
            logging={"level": "off"},
        )
        self._stagehand = stagehand
        await stagehand.browser.context.set_domain_policy(
            {"allowed_domains": _BOOKING_ALLOWED_DOMAINS}
        )
        self._page = await stagehand.browser.context.active_page()
        if self._page is None:
            raise RuntimeError("Stagehand did not expose an active page")

    def _active_page(self) -> Any:
        if self._page is None:
            raise RuntimeError("Stagehand is not attached")
        return self._page

    async def navigate(self, url: str) -> None:
        observer = await _NavigationFailureObserver.open(self._cdp_url)
        try:
            try:
                await self._active_page().goto(
                    url,
                    wait_until="domcontentloaded",
                    timeout=45_000,
                )
            except Exception as exc:
                raise BrowserNavigationFailure(
                    observer.failure or _classify_navigation_failure(str(exc))
                ) from None
            destination = await self._active_page().url()
            if urlsplit(destination).scheme.casefold() == "chrome-error":
                raise BrowserNavigationFailure(
                    observer.failure or BrowserNavigationFailureKind.UNKNOWN
                )
        finally:
            await observer.close()

    async def destination(self) -> DestinationSnapshot:
        page = self._active_page()
        stagehand = self._stagehand
        if stagehand is None:
            raise RuntimeError("Stagehand is not attached")
        pages = await stagehand.browser.context.pages()
        return DestinationSnapshot(url=await page.url(), popup_count=max(0, len(pages) - 1))

    async def viewport_size(self) -> tuple[int, int]:
        return (self._viewport_width, self._viewport_height)

    async def observe_property(
        self, property_name: str
    ) -> tuple[SemanticAction | None, ProviderUsage]:
        if self._stagehand is None:
            raise RuntimeError("Stagehand is not attached")
        started = time.monotonic()
        result = await self._stagehand.observe(
            (
                "Find the exact search result whose visible property name is "
                f"{property_name!r}. Propose only the action that opens that property's "
                "read-only hotel details in the current browser tab."
            ),
            page=self._active_page(),
            timeout=30_000,
            cache=False,
        )
        usage = _stagehand_usage(result.metadata, started)
        if not result.data:
            return None, usage
        action = result.data[0]
        return (
            SemanticAction(
                description=action.description,
                method=(action.method or "click").casefold(),
                selector=action.selector,
                token=action,
            ),
            usage,
        )

    async def inspect(self, action: SemanticAction) -> InspectedElement | None:
        selector = json.dumps(action.selector)
        expression = f"""
        (() => {{
          const selector = {selector};
          let element = null;
          try {{
            if (selector.startsWith('/') || selector.startsWith('(')) {{
              element = document.evaluate(selector, document, null,
                XPathResult.FIRST_ORDERED_NODE_TYPE, null).singleNodeValue;
            }} else {{
              element = document.querySelector(selector);
            }}
          }} catch (_) {{ return null; }}
          if (!(element instanceof Element)) return null;
          const link = element.closest('a[href]');
          const style = getComputedStyle(element);
          const rect = element.getBoundingClientRect();
          return {{
            label: (
              element.getAttribute('aria-label') || element.textContent || ''
            ).trim().slice(0, 500),
            role: (
              element.getAttribute('role') || element.tagName || ''
            ).toLowerCase().slice(0, 80),
            href: link ? link.href : null,
            visible: style.visibility !== 'hidden' &&
              style.display !== 'none' && rect.width > 0 && rect.height > 0,
            enabled: !element.hasAttribute('disabled') &&
              element.getAttribute('aria-disabled') !== 'true'
          }};
        }})()
        """
        raw = await self._active_page().evaluate(expression)
        if not isinstance(raw, Mapping):
            return None
        return InspectedElement(
            label=str(raw.get("label", ""))[:500],
            role=str(raw.get("role", ""))[:80],
            href=str(raw["href"]) if isinstance(raw.get("href"), str) else None,
            visible=raw.get("visible") is True,
            enabled=raw.get("enabled") is True,
        )

    async def replay(self, action: SemanticAction) -> None:
        if self._stagehand is None:
            raise RuntimeError("Stagehand is not attached")
        result = await self._stagehand.act(action.token, page=self._active_page(), cache=False)
        if not result.data.success:
            raise RuntimeError("guarded Stagehand action did not succeed")

    async def extract(self) -> SemanticObservationResult:
        if self._stagehand is None:
            raise RuntimeError("Stagehand is not attached")
        from pydantic import BaseModel, ConfigDict, Field

        class ExtractedOffer(BaseModel):
            model_config = ConfigDict(extra="forbid")
            room_label: str = Field(min_length=1, max_length=500)
            total: str = Field(pattern=r"^[0-9]+(?:\.[0-9]{1,2})?$")
            currency: str = Field(pattern=r"^[A-Z]{3}$")
            all_in: str
            refundability: str
            refundability_text: str | None = Field(default=None, max_length=1_000)
            completeness: str

        class ExtractedObservation(BaseModel):
            model_config = ConfigDict(extra="forbid")
            property_name: str = Field(min_length=1, max_length=500)
            property_reference: str = Field(min_length=1, max_length=300)
            check_in: str
            check_out: str
            adults: int = Field(ge=1, le=100)
            children: int = Field(ge=0, le=100)
            rooms: int = Field(ge=1, le=100)
            currency: str = Field(pattern=r"^[A-Z]{3}$")
            authenticated: bool
            genius: bool
            completeness: str
            offers: list[ExtractedOffer] = Field(min_length=1, max_length=100)

        started = time.monotonic()
        result = await self._stagehand.extract(
            (
                "Extract only visibly supported facts for the current property, stay, occupancy, "
                "signed-in/Genius context, and currently bookable room offers. total must be the "
                "explicit all-in stay total as a plain decimal string without symbols or group "
                "separators, never a nightly price. Use explicit, unknown, or "
                "conflicting evidence states; never infer refundability, identity, or currency. "
                "property_reference is the visible canonical Booking.com property URL."
            ),
            ExtractedObservation,
            page=self._active_page(),
            timeout=45_000,
            screenshot=False,
            cache=False,
        )
        usage = _stagehand_usage(result.metadata, started)
        return SemanticObservationResult(
            observation=_map_extracted_observation(result.data.model_dump()),
            usage=usage,
        )

    async def screenshot(self) -> bytes:
        region = self._next_screenshot_region
        self._next_screenshot_region = None
        options: dict[str, Any] = {
            "animations": "disabled",
            "caret": "hide",
            "full_page": False,
            "type": "png",
            "scale": "css",
        }
        if region is not None:
            x0, y0, x1, y1 = region
            options["clip"] = {
                "x": x0,
                "y": y0,
                "width": x1 - x0,
                "height": y1 - y0,
            }
        screenshot = await self._active_page().screenshot(**options)
        return cast(bytes, screenshot)

    async def hit_test(self, x: int, y: int) -> CoordinateHitTest | None:
        expression = f"""
        (() => {{
          const x = {x}; const y = {y};
          const element = document.elementFromPoint(x, y);
          if (!(element instanceof Element)) return null;
          const link = element.closest('a[href]');
          const style = getComputedStyle(element);
          const rect = element.getBoundingClientRect();
          return {{
            label: (
              element.getAttribute('aria-label') || element.textContent || ''
            ).trim().slice(0, 500),
            role: (
              element.getAttribute('role') || element.tagName || ''
            ).toLowerCase().slice(0, 80),
            href: link ? link.href : null,
            visible: style.visibility !== 'hidden' &&
              style.display !== 'none' && rect.width > 0 && rect.height > 0,
            enabled: !element.hasAttribute('disabled') &&
              element.getAttribute('aria-disabled') !== 'true',
            width: window.innerWidth, height: window.innerHeight
          }};
        }})()
        """
        raw = await self._active_page().evaluate(expression)
        if not isinstance(raw, Mapping):
            return None
        return CoordinateHitTest(
            x=x,
            y=y,
            viewport_width=int(raw.get("width", _VIEWPORT_WIDTH)),
            viewport_height=int(raw.get("height", _VIEWPORT_HEIGHT)),
            label=str(raw.get("label", ""))[:500],
            role=str(raw.get("role", ""))[:80],
            href=str(raw["href"]) if isinstance(raw.get("href"), str) else None,
            visible=raw.get("visible") is True,
            enabled=raw.get("enabled") is True,
        )

    async def focused_element(self) -> InspectedElement | None:
        raw = await self._active_page().evaluate(
            """
            (() => {
              const element = document.activeElement;
              if (!(element instanceof Element) || element === document.body) return null;
              const link = element.closest('a[href]');
              const style = getComputedStyle(element);
              const rect = element.getBoundingClientRect();
              return {
                label: (
                  element.getAttribute('aria-label') ||
                  element.getAttribute('placeholder') ||
                  element.textContent || ''
                ).trim().slice(0, 500),
                role: (
                  element.getAttribute('role') || element.tagName || ''
                ).toLowerCase().slice(0, 80),
                href: link ? link.href : null,
                visible: style.visibility !== 'hidden' &&
                  style.display !== 'none' && rect.width > 0 && rect.height > 0,
                enabled: !element.hasAttribute('disabled') &&
                  element.getAttribute('aria-disabled') !== 'true'
              };
            })()
            """
        )
        if not isinstance(raw, Mapping):
            return None
        return InspectedElement(
            label=str(raw.get("label", ""))[:500],
            role=str(raw.get("role", ""))[:80],
            href=str(raw["href"]) if isinstance(raw.get("href"), str) else None,
            visible=raw.get("visible") is True,
            enabled=raw.get("enabled") is True,
        )

    async def execute_action(self, action: ComputerActionRequest) -> None:
        page = self._active_page()
        if action.action is BrowserActionType.CLICK:
            assert action.x is not None and action.y is not None
            await page.click(action.x, action.y, button="left")
        elif action.action is BrowserActionType.SCROLL:
            await page.scroll(
                self._viewport_width / 2,
                self._viewport_height / 2,
                0,
                action.delta_y,
            )
        elif action.action is BrowserActionType.TYPE:
            assert action.value is not None
            await page.type(action.value)
        elif action.action is BrowserActionType.KEY:
            assert action.value in _SAFE_TYPED_VALUES
            await page.key_press(action.value)
        elif action.action is BrowserActionType.WAIT:
            assert action.wait_ms is not None
            await page.wait_for_timeout(action.wait_ms)
        elif action.action is BrowserActionType.ZOOM:
            assert action.zoom_region is not None
            self._next_screenshot_region = action.zoom_region

    async def verified_session_refresh(self) -> bytes | None:
        """Capture cookies only after two exact protected-resource server proofs."""
        if self._cdp_url is None:
            return None
        from playwright.async_api import async_playwright

        playwright = await async_playwright().start()
        try:
            browser = await playwright.chromium.connect_over_cdp(self._cdp_url)
            contexts = browser.contexts
            if len(contexts) != 1:
                return None
            context = contexts[0]
            for _ in range(2):
                response = await context.request.get(
                    ACCOUNT_PROBE_URL,
                    max_redirects=0,
                    fail_on_status_code=False,
                    timeout=15_000,
                )
                body = await response.body()
                if not is_authenticated_account_probe_response(
                    status=response.status,
                    headers=response.headers,
                    response_url=response.url,
                    body=body,
                ):
                    return None
            cookies = await context.cookies()
            serialized = json.dumps(
                cookies,
                ensure_ascii=True,
                separators=(",", ":"),
                sort_keys=True,
            ).encode("utf-8")
            # Reapply the same domain-only validation used before injection.
            CodeOwnedSessionBootstrap._decode_cookies(serialized)
            return serialized
        finally:
            # Disconnect this CDP client without terminating the transient Chromium instance.
            await playwright.stop()

    async def close(self) -> None:
        try:
            if self._stagehand is not None:
                await self._stagehand.close()
        finally:
            try:
                if self._browser is not None:
                    await self._browser.close()
            finally:
                if self._telemetry is not None:
                    await asyncio.to_thread(self._telemetry.close)
        self._stagehand = None
        self._browser = None
        self._page = None
        self._telemetry = None


def _stagehand_usage(metadata: Any, started: float) -> ProviderUsage:
    usage = metadata.usage
    return ProviderUsage(
        tokens=LLMUsage(
            input_tokens=int(usage.input_tokens),
            output_tokens=int(usage.output_tokens),
        ),
        latency_ms=max(0, round((time.monotonic() - started) * 1_000)),
    )


TEnum = TypeVar("TEnum", bound=Enum)


def _enum_value(enum_type: type[TEnum], raw: object) -> TEnum:
    normalized = str(raw).strip().casefold()
    for member in enum_type:
        if str(member.value).casefold() == normalized:
            return member
    raise ValueError(f"unsupported {enum_type.__name__} value")


def _map_extracted_observation(raw: Mapping[str, Any]) -> TypedObservation:
    try:
        from datetime import date

        facts = ObservedQueryFacts(
            property_name=str(raw["property_name"]),
            property_reference=str(raw["property_reference"]),
            check_in=date.fromisoformat(str(raw["check_in"])),
            check_out=date.fromisoformat(str(raw["check_out"])),
            occupancy=Occupancy(
                adults=int(raw["adults"]),
                children=int(raw["children"]),
                rooms=int(raw["rooms"]),
            ),
            currency=str(raw["currency"]),
            authenticated=raw["authenticated"] if isinstance(raw["authenticated"], bool) else None,
            genius=raw["genius"] if isinstance(raw["genius"], bool) else None,
            completeness=_enum_value(EvidenceCompleteness, raw["completeness"]),
        )
        raw_offers = raw["offers"]
        if not isinstance(raw_offers, Sequence) or isinstance(raw_offers, (str, bytes)):
            raise ValueError("offers must be a list")
        offers: list[ObservedOffer] = []
        for item in raw_offers:
            if not isinstance(item, Mapping):
                raise ValueError("offer must be an object")
            offers.append(
                ObservedOffer(
                    room_label=str(item["room_label"]),
                    total=Money.of(str(item["total"]), str(item["currency"])),
                    all_in=_enum_value(AllInEvidence, item["all_in"]),
                    refundability=_enum_value(RefundabilityEvidence, item["refundability"]),
                    refundability_text=(
                        str(item["refundability_text"])
                        if item.get("refundability_text") is not None
                        else None
                    ),
                    completeness=_enum_value(EvidenceCompleteness, item["completeness"]),
                )
            )
    except (KeyError, TypeError, ValueError, InvalidOperation) as exc:
        raise ValueError("typed price observation is invalid") from exc
    return TypedObservation(
        facts=facts,
        offers=tuple(offers),
        evidence_item_count=9 + len(offers) * 6,
    )


class AnthropicComputerUseModel:
    """Stateful Sonnet 5 computer-use conversation with only three tools."""

    def __init__(
        self,
        api_key: str,
        *,
        viewport_width: int = _VIEWPORT_WIDTH,
        viewport_height: int = _VIEWPORT_HEIGHT,
    ) -> None:
        from anthropic import Anthropic

        self._client = Anthropic(
            api_key=api_key,
            base_url=_ANTHROPIC_API_BASE,
            timeout=45.0,
            max_retries=0,
        )
        self._messages: list[dict[str, Any]] = []
        self._viewport_width = viewport_width
        self._viewport_height = viewport_height

    def next_turn(
        self,
        *,
        screenshot: bytes,
        request: PriceExecutionRequest,
        prior_tool_use_id: str | None,
    ) -> ComputerTurn:
        image = {
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": "image/png",
                "data": base64.b64encode(screenshot).decode("ascii"),
            },
        }
        if prior_tool_use_id is None:
            content: list[dict[str, Any]] = [
                {
                    "type": "text",
                    "text": _computer_goal(request),
                },
                image,
            ]
        else:
            content = [
                {
                    "type": "tool_result",
                    "tool_use_id": prior_tool_use_id,
                    "content": [image],
                }
            ]
        self._messages.append({"role": "user", "content": content})
        started = time.monotonic()
        client = cast(Any, self._client)
        response = client.beta.messages.create(
            model=_ANTHROPIC_MODEL,
            max_tokens=4_096,
            betas=[_COMPUTER_USE_BETA],
            system=(
                "You are a read-only Booking.com price observer. Never authenticate, enter "
                "credentials, solve MFA/captcha, reserve, book, pay, cancel, change, download, "
                "upload, or leave Booking.com. Use the typed submission tool only when every "
                "requested fact is visibly explicit; otherwise use a terminal tool. Every "
                "computer result already includes a fresh screenshot, so do not request the "
                "screenshot action."
            ),
            tools=_computer_tools(self._viewport_width, self._viewport_height),
            messages=self._messages,
        )
        elapsed = max(0, round((time.monotonic() - started) * 1_000))
        usage = ProviderUsage(
            tokens=LLMUsage(
                input_tokens=int(response.usage.input_tokens),
                output_tokens=int(response.usage.output_tokens),
            ),
            latency_ms=elapsed,
        )
        assistant_content = [
            block.model_dump(exclude_none=True) if hasattr(block, "model_dump") else block
            for block in response.content
        ]
        self._messages.append({"role": "assistant", "content": assistant_content})
        tool_blocks: list[Any] = [
            block for block in response.content if getattr(block, "type", None) == "tool_use"
        ]
        if len(tool_blocks) != 1:
            raise ValueError("computer use must return exactly one tool call")
        block = tool_blocks[0]
        name = str(block.name)
        tool_input = block.input
        if not isinstance(tool_input, Mapping):
            raise ValueError("computer tool input must be an object")
        if name == "computer":
            try:
                action = _parse_computer_action(str(block.id), tool_input)
            except (TypeError, ValueError):
                return ComputerTurn(
                    ComputerTurnKind.TERMINAL,
                    usage,
                    terminal_status=PriceExecutionStatus.UNSAFE_ACTION,
                )
            return ComputerTurn(ComputerTurnKind.ACTION, usage, action=action)
        if name == "submit_price_observation":
            return ComputerTurn(
                ComputerTurnKind.SUBMISSION,
                usage,
                observation=_map_extracted_observation(tool_input),
            )
        if name == "submit_terminal_outcome":
            return ComputerTurn(
                ComputerTurnKind.TERMINAL,
                usage,
                terminal_status=_terminal_status(tool_input.get("status")),
            )
        raise ValueError("unapproved computer-use tool")


def _computer_goal(request: PriceExecutionRequest) -> str:
    query = request.query
    return (
        "Observe the currently open Booking.com page for this trusted query: "
        f"property={query.property_name!r}; check-in={query.stay_dates.check_in.isoformat()}; "
        f"check-out={query.stay_dates.check_out.isoformat()}; adults={query.occupancy.adults}; "
        f"children={query.occupancy.children}; rooms={query.occupancy.rooms}; "
        f"currency={query.currency}. Navigate only with the computer tool already on this page. "
        "Submit visible all-in refundable offers and explicit signed-in/Genius evidence."
    )


def _observation_schema() -> dict[str, Any]:
    offer = {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "room_label",
            "total",
            "currency",
            "all_in",
            "refundability",
            "refundability_text",
            "completeness",
        ],
        "properties": {
            "room_label": {"type": "string", "minLength": 1, "maxLength": 500},
            "total": {
                "type": "string",
                "pattern": r"^[0-9]+(?:\.[0-9]{1,2})?$",
            },
            "currency": {"type": "string", "pattern": "^[A-Z]{3}$"},
            "all_in": {"enum": [item.value for item in AllInEvidence]},
            "refundability": {"enum": [item.value for item in RefundabilityEvidence]},
            "refundability_text": {"type": ["string", "null"], "maxLength": 1_000},
            "completeness": {"enum": [item.value for item in EvidenceCompleteness]},
        },
    }
    return {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "property_name",
            "property_reference",
            "check_in",
            "check_out",
            "adults",
            "children",
            "rooms",
            "currency",
            "authenticated",
            "genius",
            "completeness",
            "offers",
        ],
        "properties": {
            "property_name": {"type": "string", "minLength": 1, "maxLength": 500},
            "property_reference": {"type": "string", "minLength": 1, "maxLength": 300},
            "check_in": {"type": "string", "format": "date"},
            "check_out": {"type": "string", "format": "date"},
            "adults": {"type": "integer", "minimum": 1, "maximum": 100},
            "children": {"type": "integer", "minimum": 0, "maximum": 100},
            "rooms": {"type": "integer", "minimum": 1, "maximum": 100},
            "currency": {"type": "string", "pattern": "^[A-Z]{3}$"},
            "authenticated": {"type": "boolean"},
            "genius": {"type": "boolean"},
            "completeness": {"enum": [item.value for item in EvidenceCompleteness]},
            "offers": {"type": "array", "minItems": 1, "maxItems": 100, "items": offer},
        },
    }


def _computer_tools(
    viewport_width: int = _VIEWPORT_WIDTH,
    viewport_height: int = _VIEWPORT_HEIGHT,
) -> list[dict[str, Any]]:
    return [
        {
            "type": "computer_20251124",
            "name": "computer",
            "display_width_px": viewport_width,
            "display_height_px": viewport_height,
            "enable_zoom": True,
            "strict": True,
        },
        {
            "name": "submit_price_observation",
            "description": "Submit complete visible Booking.com price evidence.",
            "input_schema": _observation_schema(),
            "strict": True,
        },
        {
            "name": "submit_terminal_outcome",
            "description": "Stop with one closed non-success outcome.",
            "input_schema": {
                "type": "object",
                "additionalProperties": False,
                "required": ["status"],
                "properties": {
                    "status": {
                        "enum": [
                            PriceExecutionStatus.SIGNED_OUT.value,
                            PriceExecutionStatus.MFA_REQUIRED.value,
                            PriceExecutionStatus.CAPTCHA.value,
                            PriceExecutionStatus.BOT_WALL.value,
                            PriceExecutionStatus.UNAVAILABLE.value,
                            PriceExecutionStatus.NO_VALID_OBSERVATION.value,
                            PriceExecutionStatus.PROVIDER_FAILURE.value,
                            PriceExecutionStatus.BUDGET_EXHAUSTED.value,
                            PriceExecutionStatus.TIMEOUT.value,
                        ]
                    }
                },
            },
            "strict": True,
        },
    ]


def _parse_computer_action(tool_use_id: str, raw: Mapping[str, Any]) -> ComputerActionRequest:
    action_name = str(raw.get("action", "")).casefold()
    if action_name == "screenshot":
        raise ValueError("screenshot is supplied automatically and is not an action turn")
    if action_name in {"left_click", "click"}:
        coordinate = raw.get("coordinate")
        if not isinstance(coordinate, Sequence) or len(coordinate) != 2:
            raise ValueError("click coordinate is required")
        return ComputerActionRequest(
            BrowserActionType.CLICK,
            tool_use_id,
            x=int(coordinate[0]),
            y=int(coordinate[1]),
        )
    if action_name == "scroll":
        amount = int(raw.get("scroll_amount", raw.get("amount", 0)))
        direction = str(raw.get("scroll_direction", raw.get("direction", "down"))).casefold()
        if direction not in {"up", "down"}:
            raise ValueError("horizontal computer scrolling is prohibited")
        return ComputerActionRequest(
            BrowserActionType.SCROLL,
            tool_use_id,
            delta_y=(amount * 100) if direction == "down" else -(amount * 100),
        )
    if action_name == "type":
        return ComputerActionRequest(
            BrowserActionType.TYPE,
            tool_use_id,
            value=str(raw.get("text", "")),
        )
    if action_name in {"key", "key_press"}:
        return ComputerActionRequest(
            BrowserActionType.KEY,
            tool_use_id,
            value=str(raw.get("text", raw.get("key", ""))),
        )
    if action_name == "wait":
        wait_ms = (
            int(raw["duration_ms"])
            if "duration_ms" in raw
            else round(float(raw.get("duration", 1.0)) * 1_000)
        )
        return ComputerActionRequest(
            BrowserActionType.WAIT,
            tool_use_id,
            wait_ms=wait_ms,
        )
    if action_name == "zoom":
        region = raw.get("region")
        if (
            not isinstance(region, Sequence)
            or isinstance(region, (str, bytes))
            or len(region) != 4
        ):
            raise ValueError("zoom region is required")
        return ComputerActionRequest(
            BrowserActionType.ZOOM,
            tool_use_id,
            zoom_region=cast(tuple[int, int, int, int], tuple(int(value) for value in region)),
        )
    raise ValueError("computer action is not approved")


def _terminal_status(raw: object) -> PriceExecutionStatus:
    status = PriceExecutionStatus(str(raw))
    if status is PriceExecutionStatus.OBSERVED:
        raise ValueError("terminal tool cannot submit an observation")
    return status


def build_trusted_search_url(request: PriceExecutionRequest) -> str:
    query = request.query
    params = {
        "ss": query.property_name,
        "checkin": query.stay_dates.check_in.isoformat(),
        "checkout": query.stay_dates.check_out.isoformat(),
        "group_adults": str(query.occupancy.adults),
        "group_children": str(query.occupancy.children),
        "no_rooms": str(query.occupancy.rooms),
        "selected_currency": query.currency,
        "sb": "1",
        "src": "searchresults",
    }
    url = f"https://www.booking.com/searchresults.html?{urlencode(params)}"
    if classify_executor_egress(url) is not ExecutorEgressKind.BOOKING:
        raise RuntimeError("trusted search destination is outside the executor allowlist")
    return url


def _trusted_input_values(request: PriceExecutionRequest) -> frozenset[str]:
    """Return the exact code-owned values a visual episode may type into the page."""
    query = request.query
    return frozenset(
        {
            query.property_name,
            query.stay_dates.check_in.isoformat(),
            query.stay_dates.check_out.isoformat(),
            str(query.occupancy.adults),
            str(query.occupancy.children),
            str(query.occupancy.rooms),
            query.currency,
        }
    )


class StagehandPriceBrowserExecutor:
    """Synchronous port adapter over one isolated semantic/visual async episode."""

    def __init__(
        self,
        *,
        api_key: str,
        lease_broker: InMemorySessionLeaseBroker,
        budget: BrowserJobCostBudget,
        runner: AsyncLoopRunner,
        runtime_factory: Callable[[], StagehandRuntimePort] = LocalStagehandRuntime,
        computer_model_factory: Callable[[], ComputerUseModelPort] | None = None,
        guard: BrowserActionGuard | None = None,
    ) -> None:
        if not api_key.strip():
            raise ValueError("BOOKSAVER_LLM_API_KEY is required for agentic routing")
        self._api_key = api_key
        self._leases = lease_broker
        self._budget = budget
        self._runner = runner
        self._runtime_factory = runtime_factory
        self._computer_model_factory = computer_model_factory
        self._guard = guard or BrowserActionGuard()

    def execute(self, request: PriceExecutionRequest) -> PriceExecutionResult:
        remaining = (request.limits.deadline - datetime.now(UTC)).total_seconds()
        timeout = max(0.001, min(float(request.limits.timeout_seconds), remaining))
        started = time.monotonic()
        meter = ExecutionMeter(request.limits)
        finished = threading.Event()
        try:
            return self._runner.run(
                self._execute(request, started, meter, finished),
                timeout=timeout,
            )
        except TimeoutError:
            finished.wait(timeout=5)
            return PriceExecutionResult(
                PriceExecutionStatus.TIMEOUT,
                usage=meter.snapshot(),
                latency_ms=max(0, round((time.monotonic() - started) * 1_000)),
            )
        except Exception as exc:
            logger.warning(
                "Agentic price execution failed execution_id=%s failure_type=%s",
                request.execution_id,
                type(exc).__name__,
            )
            return PriceExecutionResult(
                PriceExecutionStatus.PROVIDER_FAILURE,
                usage=meter.snapshot(),
                latency_ms=max(0, round((time.monotonic() - started) * 1_000)),
            )

    async def _execute(
        self,
        request: PriceExecutionRequest,
        started: float,
        meter: ExecutionMeter,
        finished: threading.Event,
    ) -> PriceExecutionResult:
        runtime = self._runtime_factory()
        fallback_used = False
        try:
            await runtime.launch()
            self._leases.restore_into(request.session_lease, runtime)
            await runtime.apply_session()
            await runtime.attach(self._api_key)

            before = await runtime.destination()
            meter.record_action()
            try:
                await runtime.navigate(build_trusted_search_url(request))
            except BrowserNavigationFailure as exc:
                logger.warning(
                    "Agentic price navigation failed execution_id=%s phase=entry "
                    "failure_category=%s",
                    request.execution_id,
                    exc.kind.value,
                )
                return self._terminal(
                    PriceExecutionStatus.PROVIDER_FAILURE,
                    meter,
                    started,
                )
            navigation = self._guard.validate_destination(
                before,
                await runtime.destination(),
            )
            if not navigation.allowed:
                violations = (
                    frozenset({ExecutorSafetyViolation.NON_ALLOWLISTED_DESTINATION})
                    if navigation.rejection is GuardRejection.INVALID_DESTINATION
                    else frozenset()
                )
                return self._terminal(
                    PriceExecutionStatus.UNSAFE_ACTION,
                    meter,
                    started,
                    safety_violations=violations,
                )

            semantic = await self._semantic_episode(runtime, request, meter)
            if isinstance(semantic, TypedObservation):
                result = self._observed(
                    semantic,
                    ObservationSource.STAGEHAND_EXTRACT,
                    meter,
                    started,
                    fallback_used=False,
                )
                return await self._with_verified_refresh(runtime, request, result, started)
            if semantic is SemanticFailure.DESTINATION_CHANGED:
                return self._terminal(
                    PriceExecutionStatus.UNSAFE_ACTION,
                    meter,
                    started,
                    safety_violations=frozenset(
                        {ExecutorSafetyViolation.PROHIBITED_ACTION_EXECUTED}
                    ),
                )
            if semantic is SemanticFailure.NON_ALLOWLISTED_DESTINATION:
                return self._terminal(
                    PriceExecutionStatus.UNSAFE_ACTION,
                    meter,
                    started,
                    safety_violations=frozenset(
                        {
                            ExecutorSafetyViolation.PROHIBITED_ACTION_EXECUTED,
                            ExecutorSafetyViolation.NON_ALLOWLISTED_DESTINATION,
                        }
                    ),
                )

            fallback_used = True
            result = await self._computer_episode(runtime, request, meter, started)
            return await self._with_verified_refresh(runtime, request, result, started)
        except RuntimeError as exc:
            status = (
                PriceExecutionStatus.BUDGET_EXHAUSTED
                if "limit exhausted" in str(exc)
                else PriceExecutionStatus.PROVIDER_FAILURE
            )
            return self._terminal(status, meter, started, fallback_used=fallback_used)
        finally:
            try:
                await runtime.close()
            except Exception as exc:
                logger.warning(
                    "Agentic browser cleanup failed execution_id=%s failure_type=%s",
                    request.execution_id,
                    type(exc).__name__,
                )
            finally:
                finished.set()

    async def _with_verified_refresh(
        self,
        runtime: StagehandRuntimePort,
        request: PriceExecutionRequest,
        result: PriceExecutionResult,
        started: float,
    ) -> PriceExecutionResult:
        if result.status is not PriceExecutionStatus.OBSERVED:
            return result
        try:
            refreshed = await runtime.verified_session_refresh()
            if refreshed is None:
                return PriceExecutionResult(
                    PriceExecutionStatus.SESSION_UNAVAILABLE,
                    usage=result.usage,
                    latency_ms=max(0, round((time.monotonic() - started) * 1_000)),
                    fallback_used=result.fallback_used,
                )
            self._leases.store_verified_refresh(request.session_lease, refreshed)
            return replace(result, refreshed_session_eligible=True)
        except Exception as exc:
            logger.warning(
                "Agentic session refresh proof failed execution_id=%s failure_type=%s",
                request.execution_id,
                type(exc).__name__,
            )
            return PriceExecutionResult(
                PriceExecutionStatus.SESSION_UNAVAILABLE,
                usage=result.usage,
                latency_ms=max(0, round((time.monotonic() - started) * 1_000)),
                fallback_used=result.fallback_used,
            )

    async def _semantic_episode(
        self,
        runtime: StagehandRuntimePort,
        request: PriceExecutionRequest,
        meter: ExecutionMeter,
    ) -> TypedObservation | SemanticFailure:
        admitted = self._admit(ModelRole.RECOVERY, "stagehand-observe-v1")
        if admitted is None:
            return SemanticFailure.ACTION_FAILED
        try:
            action, usage = await runtime.observe_property(request.query.property_name)
        except asyncio.CancelledError:
            self._reconcile_failure(admitted, meter)
            raise
        except Exception:
            self._reconcile_failure(admitted, meter)
            return SemanticFailure.ACTION_FAILED
        self._reconcile_success(admitted, usage, meter)
        if action is None:
            return SemanticFailure.NO_ACTION
        if action.method not in {"click", "locator.click"}:
            return SemanticFailure.PROPOSAL_REJECTED
        inspected = await runtime.inspect(action)
        if inspected is None or not inspected.visible or not inspected.enabled:
            return SemanticFailure.PROPOSAL_REJECTED
        before = await runtime.destination()
        proposal = BrowserActionProposal(
            action=BrowserActionType.CLICK,
            current=before,
            label=f"{action.description} {inspected.label}",
            role=inspected.role,
            destination=inspected.href,
        )
        if not self._guard.evaluate(proposal).allowed:
            return SemanticFailure.PROPOSAL_REJECTED
        meter.record_action()
        try:
            await runtime.replay(action)
        except Exception:
            return SemanticFailure.ACTION_FAILED
        post_action = self._guard.validate_destination(before, await runtime.destination())
        if not post_action.allowed:
            if post_action.rejection is GuardRejection.INVALID_DESTINATION:
                return SemanticFailure.NON_ALLOWLISTED_DESTINATION
            return SemanticFailure.DESTINATION_CHANGED

        admitted = self._admit(ModelRole.EXTRACTION, "stagehand-price-extract-v1")
        if admitted is None:
            return SemanticFailure.EXTRACTION_INVALID
        try:
            extracted = await runtime.extract()
        except asyncio.CancelledError:
            self._reconcile_failure(admitted, meter)
            raise
        except Exception:
            self._reconcile_failure(admitted, meter)
            return SemanticFailure.EXTRACTION_INVALID
        self._reconcile_success(admitted, extracted.usage, meter)
        return extracted.observation

    async def _computer_episode(
        self,
        runtime: StagehandRuntimePort,
        request: PriceExecutionRequest,
        meter: ExecutionMeter,
        started: float,
    ) -> PriceExecutionResult:
        viewport_width, viewport_height = await runtime.viewport_size()
        model = (
            self._computer_model_factory()
            if self._computer_model_factory is not None
            else AnthropicComputerUseModel(
                self._api_key,
                viewport_width=viewport_width,
                viewport_height=viewport_height,
            )
        )
        prior_tool_use_id: str | None = None
        while True:
            admitted = self._admit(ModelRole.RECOVERY, "anthropic-computer-use-price-v1")
            if admitted is None:
                return self._terminal(
                    PriceExecutionStatus.BUDGET_EXHAUSTED,
                    meter,
                    started,
                    fallback_used=True,
                )
            screenshot = await runtime.screenshot()
            try:
                turn = await asyncio.to_thread(
                    model.next_turn,
                    screenshot=screenshot,
                    request=request,
                    prior_tool_use_id=prior_tool_use_id,
                )
            except asyncio.CancelledError:
                self._reconcile_failure(admitted, meter)
                raise
            except Exception:
                self._reconcile_failure(admitted, meter)
                return self._terminal(
                    PriceExecutionStatus.PROVIDER_FAILURE,
                    meter,
                    started,
                    fallback_used=True,
                )
            self._reconcile_success(admitted, turn.usage, meter)
            if turn.kind is ComputerTurnKind.SUBMISSION:
                assert turn.observation is not None
                return self._observed(
                    turn.observation,
                    ObservationSource.COMPUTER_USE_SUBMISSION,
                    meter,
                    started,
                    fallback_used=True,
                )
            if turn.kind is ComputerTurnKind.TERMINAL:
                assert turn.terminal_status is not None
                return self._terminal(
                    turn.terminal_status,
                    meter,
                    started,
                    fallback_used=True,
                )
            assert turn.action is not None
            if (
                meter.snapshot().computer_use_actions
                >= request.limits.max_computer_use_actions
            ):
                return self._terminal(
                    PriceExecutionStatus.BUDGET_EXHAUSTED,
                    meter,
                    started,
                    fallback_used=True,
                )
            before = await runtime.destination()
            proposal = await self._computer_proposal(
                runtime,
                before,
                turn.action,
                request,
            )
            decision = self._guard.evaluate(proposal)
            if not decision.allowed:
                logger.info(
                    "Agentic action rejected execution_id=%s code=%s",
                    request.execution_id,
                    (decision.rejection or GuardRejection.UNSUPPORTED_ACTION).value,
                )
                return self._terminal(
                    PriceExecutionStatus.UNSAFE_ACTION,
                    meter,
                    started,
                    fallback_used=True,
                )
            meter.record_action(computer_use=True)
            await runtime.execute_action(turn.action)
            post_action = self._guard.validate_destination(
                before,
                await runtime.destination(),
            )
            if not post_action.allowed:
                violations = {ExecutorSafetyViolation.PROHIBITED_ACTION_EXECUTED}
                if post_action.rejection is GuardRejection.INVALID_DESTINATION:
                    violations.add(ExecutorSafetyViolation.NON_ALLOWLISTED_DESTINATION)
                return self._terminal(
                    PriceExecutionStatus.UNSAFE_ACTION,
                    meter,
                    started,
                    fallback_used=True,
                    safety_violations=frozenset(violations),
                )
            prior_tool_use_id = turn.action.tool_use_id

    async def _computer_proposal(
        self,
        runtime: StagehandRuntimePort,
        current: DestinationSnapshot,
        action: ComputerActionRequest,
        request: PriceExecutionRequest,
    ) -> BrowserActionProposal:
        hit = None
        label = ""
        role = ""
        destination = None
        if action.action is BrowserActionType.CLICK:
            assert action.x is not None and action.y is not None
            hit = await runtime.hit_test(action.x, action.y)
            if hit is not None:
                label, role, destination = hit.label, hit.role, hit.href
        elif action.action is BrowserActionType.TYPE:
            focused = await runtime.focused_element()
            if focused is not None:
                label, role, destination = focused.label, focused.role, focused.href
            if action.value not in _trusted_input_values(request):
                return BrowserActionProposal(
                    action=action.action,
                    current=current,
                    label=label,
                    role=role,
                    destination=destination,
                    value=None,
                )
        viewport_width, viewport_height = await runtime.viewport_size()
        return BrowserActionProposal(
            action=action.action,
            current=current,
            label=label,
            role=role,
            destination=destination,
            value=action.value,
            x=action.x,
            y=action.y,
            delta_y=action.delta_y,
            wait_ms=action.wait_ms,
            zoom_region=action.zoom_region,
            viewport_width=viewport_width,
            viewport_height=viewport_height,
            hit_test=hit,
        )

    def _admit(self, role: ModelRole, prompt_version: str) -> AdmittedModelAttempt | None:
        profile = AdaptiveModelPortfolio().primary(role, prompt_version)
        admission = self._budget.admit(
            ModelAttemptPlan(1, profile, EscalationTrigger.INITIAL_AMBIGUOUS),
            _MODEL_ENVELOPE,
        )
        return admission.attempt

    def _reconcile_success(
        self,
        admitted: AdmittedModelAttempt,
        usage: ProviderUsage,
        meter: ExecutionMeter,
    ) -> None:
        reconciliation = self._budget.reconcile(
            admitted,
            usage=usage.tokens,
            latency_ms=usage.latency_ms,
            outcome=ModelAttemptOutcome.COMPLETED,
        )
        meter.record_model_call(usage.tokens, reconciliation.charged_cost)

    def _reconcile_failure(
        self,
        admitted: AdmittedModelAttempt,
        meter: ExecutionMeter,
    ) -> None:
        reconciliation = self._budget.reconcile(
            admitted,
            usage=None,
            latency_ms=0,
            outcome=ModelAttemptOutcome.PROVIDER_FAILED,
        )
        meter.record_model_call(LLMUsage(), reconciliation.charged_cost)

    @staticmethod
    def _observed(
        observation: TypedObservation,
        source: ObservationSource,
        meter: ExecutionMeter,
        started: float,
        *,
        fallback_used: bool,
    ) -> PriceExecutionResult:
        usage = meter.snapshot()
        return PriceExecutionResult(
            PriceExecutionStatus.OBSERVED,
            query_facts=observation.facts,
            offers=observation.offers,
            provenance=RedactedProvenance(
                source=source,
                action_count=usage.total_actions,
                evidence_item_count=observation.evidence_item_count,
            ),
            refreshed_session_eligible=False,
            usage=usage,
            latency_ms=max(0, round((time.monotonic() - started) * 1_000)),
            fallback_used=fallback_used,
        )

    @staticmethod
    def _terminal(
        status: PriceExecutionStatus,
        meter: ExecutionMeter,
        started: float,
        *,
        fallback_used: bool = False,
        safety_violations: frozenset[ExecutorSafetyViolation] = frozenset(),
    ) -> PriceExecutionResult:
        usage = meter.snapshot()
        return PriceExecutionResult(
            status,
            usage=usage,
            latency_ms=max(0, round((time.monotonic() - started) * 1_000)),
            fallback_used=fallback_used,
            safety_violations=safety_violations,
        )


class LocalAgenticPriceExecutor:
    """One-shot executor that owns and closes its dedicated async runner."""

    def __init__(
        self,
        *,
        api_key: str,
        lease_broker: InMemorySessionLeaseBroker,
        budget: BrowserJobCostBudget,
        mobile_settings: MobileWebSettings | None = None,
    ) -> None:
        self._api_key = api_key
        self._leases = lease_broker
        self._budget = budget
        self._mobile_settings = mobile_settings or MobileWebSettings()

    def execute(self, request: PriceExecutionRequest) -> PriceExecutionResult:
        with AsyncLoopRunner() as runner:
            return StagehandPriceBrowserExecutor(
                api_key=self._api_key,
                lease_broker=self._leases,
                budget=self._budget,
                runner=runner,
                runtime_factory=lambda: LocalStagehandRuntime(self._mobile_settings),
            ).execute(request)
