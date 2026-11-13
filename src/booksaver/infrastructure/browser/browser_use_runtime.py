"""Shared hardened Browser Use runtime infrastructure.

The host owns one transient local browser session and its confinement lifecycle. Price and
inventory executors own separate action registries, episode state, and typed result mapping.
"""

from __future__ import annotations

import asyncio
import base64
import io
import json
import logging
import os
import re
import shutil
import tempfile
import time
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any, Protocol, cast
from urllib.parse import parse_qsl, unquote, urljoin, urlsplit

from booksaver.domain.browser_executor import ExecutionLimits
from booksaver.domain.browser_guard import ExecutorEgressKind, classify_executor_egress
from booksaver.domain.mobile_web import MobileWebSettings
from booksaver.domain.session_maintenance import (
    SessionVerificationOutcome,
    SessionVerificationResult,
)
from booksaver.infrastructure.browser.session_bootstrap import CodeOwnedSessionBootstrap
from booksaver.infrastructure.browser.session_maintenance import (
    unexpired_cookie_material,
    verify_saved_snapshot,
)
from booksaver.infrastructure.remote_auth.network_session import ACCOUNT_PROBE_URL

logger = logging.getLogger(__name__)

ALLOWED_DOMAINS = ["booking.com", "*.booking.com"]
_ACCOUNT_AUTH_SETTLE_MILLISECONDS = (5_000, 3_000)
_UNSAFE_WATCHDOG_PREFIXES = (
    "DownloadsWatchdog.",
    "StorageStateWatchdog.",
    "AboutBlankWatchdog.",
    "PopupsWatchdog.",
    "PermissionsWatchdog.",
)
_UNSAFE_ROUTE_TERMS = re.compile(
    r"(?:^|[^a-z0-9])(?:login|signin|sign-in|auth|oauth|password|mfa|captcha|challenge|"
    r"cancel|modify|change|edit|delete|remove|checkout|payment|purchase|pay|book-now|"
    r"reserve|upload|download|install|print)(?:[^a-z0-9]|$)",
    re.IGNORECASE,
)
_UNSAFE_QUERY_TERMS = re.compile(
    r"(?:^|[^a-z0-9])(?:cancel|modify|change|edit|delete|remove|checkout|payment|"
    r"purchase|pay|book-now|reserve|upload|download|install|print)(?:[^a-z0-9]|$)",
    re.IGNORECASE,
)
UNSAFE_LABEL_TERMS = re.compile(
    r"(?:^|\b)(?:sign\s*in|log\s*in|password|verification|security code|mfa|captcha|"
    r"cancel(?:lation)?|modify|change|edit|delete|remove|book\s*(?:now|again)|reserve|"
    r"checkout|pay(?:ment)?|purchase|submit|upload|download|print|confirm)(?:\b|$)",
    re.IGNORECASE,
)
_CONFIG_DIR = Path(tempfile.gettempdir()) / "booksaver-browser-use-config"
_CACHE_DIR = Path(tempfile.gettempdir()) / "booksaver-browser-use-cache"
_SILENCED_LOGGERS = (
    "browser_use",
    "browser_use_sdk",
    "bubus",
    "cdp_use",
    "posthog",
)

def is_unsafe_watchdog_handler(handler: object) -> bool:
    """Recognize qualified Browser Use wrappers and ordinary bound handlers."""

    candidates = {
        str(getattr(handler, "__name__", "")),
        str(getattr(handler, "__qualname__", "")),
    }
    bound_owner = getattr(handler, "__self__", None)
    if bound_owner is not None:
        candidates.add(type(bound_owner).__name__)
    for prefix in _UNSAFE_WATCHDOG_PREFIXES:
        owner = prefix.removesuffix(".")
        if any(
            candidate == owner
            or candidate.startswith(prefix)
            or f".{prefix}" in candidate
            for candidate in candidates
        ):
            return True
    return False


def prepare_browser_use_environment() -> None:
    """Set confinement flags before the first Browser Use import."""

    values = {
        "ANONYMIZED_TELEMETRY": "false",
        "BROWSER_USE_CLOUD_SYNC": "false",
        "BROWSER_USE_VERSION_CHECK": "false",
        "BROWSER_USE_SETUP_LOGGING": "false",
        "BROWSER_USE_CALCULATE_COST": "false",
        "BROWSER_USE_DISABLE_EXTENSIONS": "1",
        "BROWSER_USE_CONFIG_DIR": str(_CONFIG_DIR),
        "XDG_CACHE_HOME": str(_CACHE_DIR),
    }
    for key, value in values.items():
        os.environ[key] = value
    for directory in (_CONFIG_DIR, _CACHE_DIR):
        directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        directory.chmod(0o700)
    for name in _SILENCED_LOGGERS:
        dependency_logger = logging.getLogger(name)
        dependency_logger.handlers[:] = [logging.NullHandler()]
        dependency_logger.propagate = False
        dependency_logger.disabled = True


def browser_request_allowed(url: str) -> bool:
    try:
        parsed = urlsplit(url)
        port = parsed.port
    except ValueError:
        return False
    if parsed.scheme.casefold() in {"data", "blob", "about"}:
        return parsed.username is None and parsed.password is None
    host = (parsed.hostname or "").casefold().rstrip(".")
    if (
        parsed.scheme.casefold() == "https"
        and parsed.username is None
        and parsed.password is None
        and port in {None, 443}
        and host.endswith(".token.awswaf.com")
        and host != "token.awswaf.com"
    ):
        # Booking.com's authenticated trips bootstrap currently requires an AWS WAF challenge
        # token subresource. It is never an observable or agent-navigable destination, and
        # Booking-domain cookies cannot be sent to this unrelated cookie domain.
        return True
    if (
        parsed.scheme.casefold() == "wss"
        and parsed.username is None
        and parsed.password is None
        and port in {None, 443}
        and (
            host == "booking.com"
            or host.endswith(".booking.com")
            or host == "bstatic.com"
            or host.endswith(".bstatic.com")
        )
    ):
        return True
    return classify_executor_egress(url) in {
        ExecutorEgressKind.BOOKING,
        ExecutorEgressKind.LOOPBACK,
    }


@dataclass(frozen=True, slots=True)
class ClickChainDecision:
    allowed: bool
    reason: str
    depth: int


_INTERACTIVE_CLICK_ROLES = frozenset(
    {
        "a",
        "button",
        "input",
        "link",
        "menuitem",
        "option",
        "select",
        "tab",
        "textarea",
    }
)
_INTERACTIVE_CLICK_ATTRIBUTES = frozenset(
    {"action", "download", "formaction", "href", "role", "target", "type"}
)


def _is_interactive_click_node(role: str, attributes: Mapping[str, object]) -> bool:
    normalized_role = role.strip().casefold()
    normalized_keys = {str(key).casefold() for key in attributes}
    return (
        normalized_role in _INTERACTIVE_CLICK_ROLES
        or bool(normalized_keys & _INTERACTIVE_CLICK_ATTRIBUTES)
        or any(key.startswith("on") for key in normalized_keys)
    )


def node_chain_click_decision(
    guard: BrowserUseActionGuard,
    *,
    node: object,
    current_url: str,
    active_target_id: str | None,
) -> ClickChainDecision:
    current: object | None = node
    seen: set[int] = set()
    depth = 0
    interactive_seen = False
    while current is not None:
        depth += 1
        identity = id(current)
        if depth > 32:
            return ClickChainDecision(False, "chain_depth", depth)
        if identity in seen:
            return ClickChainDecision(False, "chain_cycle", depth)
        seen.add(identity)
        target_id = getattr(current, "target_id", active_target_id)
        if active_target_id is None or target_id != active_target_id:
            return ClickChainDecision(False, "target_mismatch", depth)
        if getattr(current, "is_visible", True) is False:
            return ClickChainDecision(False, "hidden_node", depth)
        attributes = getattr(current, "attributes", {}) or {}
        if not isinstance(attributes, Mapping):
            return ClickChainDecision(False, "invalid_attributes", depth)
        meaningful_text = getattr(current, "get_meaningful_text_for_llm", None)
        try:
            raw_label = str(meaningful_text()) if callable(meaningful_text) else ""
        except Exception:
            return ClickChainDecision(False, "label_error", depth)
        role = str(attributes.get("role", getattr(current, "node_name", "")))
        interactive = _is_interactive_click_node(role, attributes)
        interactive_seen = interactive_seen or interactive
        # Browser Use's meaningful text for structural ancestors is aggregate descendant text.
        # It can be arbitrarily large and unrelated to the clicked control.  Inspect the selected
        # node and every interactive ancestor, while retaining attribute/role checks for all
        # structural ancestors so nested links, forms, event handlers and destinations stay guarded.
        label = raw_label if depth == 1 or interactive else ""
        rejection = guard.click_rejection_reason(
            current_url=current_url,
            label=label,
            role=role,
            attributes=attributes,
        )
        if rejection is not None:
            return ClickChainDecision(False, f"guard_{rejection}", depth)
        current = getattr(current, "parent_node", None)
    if not interactive_seen:
        return ClickChainDecision(False, "no_interactive_ancestor", depth)
    return ClickChainDecision(True, "allowed", depth)


def coordinate_chain_click_decision(
    guard: BrowserUseActionGuard,
    *,
    chain: list[Mapping[str, object]],
    current_url: str,
) -> ClickChainDecision:
    """Apply the same generic click policy to a browser hit-tested ancestor chain."""

    if not chain or len(chain) > 16:
        return ClickChainDecision(False, "coordinate_chain_bounds", len(chain))
    interactive_seen = False
    for depth, item in enumerate(chain, start=1):
        if item.get("visible") is not True:
            return ClickChainDecision(False, "hidden_node", depth)
        attributes = item.get("attributes", {})
        if not isinstance(attributes, Mapping):
            return ClickChainDecision(False, "invalid_attributes", depth)
        role = str(attributes.get("role", item.get("node_name", "")))
        interactive = _is_interactive_click_node(role, attributes)
        interactive_seen = interactive_seen or interactive
        raw_label = str(item.get("label", ""))
        label = raw_label if depth == 1 or interactive else ""
        rejection = guard.click_rejection_reason(
            current_url=current_url,
            label=label,
            role=role,
            attributes=attributes,
        )
        if rejection is not None:
            return ClickChainDecision(False, f"guard_{rejection}", depth)
    if not interactive_seen:
        return ClickChainDecision(False, "no_interactive_ancestor", len(chain))
    return ClickChainDecision(True, "allowed", len(chain))


def same_tab_click_destination(
    guard: BrowserUseActionGuard,
    *,
    node: object,
    current_url: str,
) -> str | None:
    """Return one guarded destination when a safe link would otherwise open a popup."""

    current: object | None = node
    seen: set[int] = set()
    for _ in range(32):
        if current is None:
            return None
        identity = id(current)
        if identity in seen:
            return None
        seen.add(identity)
        attributes = getattr(current, "attributes", {}) or {}
        if not isinstance(attributes, Mapping):
            return None
        if str(attributes.get("target", "")).casefold() == "_blank":
            href = attributes.get("href")
            if not isinstance(href, str) or not href:
                return None
            destination = urljoin(current_url, href)
            return destination if guard.observable_url(destination) else None
        current = getattr(current, "parent_node", None)
    return None


async def remember_visible_semantic_state(
    browser_session: Any,
    snapshots: list[str],
    *,
    log_failure: bool = False,
) -> bool:
    try:
        state = await browser_session.get_browser_state_summary(
            include_screenshot=False,
            cached=False,
            include_recent_events=False,
        )
        visible_dom = state.dom_state.llm_representation()
    except Exception as exc:
        if log_failure:
            logger.warning(
                "Browser Use semantic state unavailable failure_type=%s",
                type(exc).__name__,
            )
        return False
    if not visible_dom:
        return False
    visible_dom = visible_dom[:250_000]
    if not snapshots or snapshots[-1] != visible_dom:
        snapshots.append(visible_dom)
        del snapshots[:-6]
    return True


async def browser_use_screenshot_available(browser_session: Any) -> bool:
    """Confirm that the harness can provide current visual state without persisting it."""

    try:
        state = await browser_session.get_browser_state_summary(
            include_screenshot=True,
            cached=False,
            include_recent_events=False,
        )
    except Exception:
        return False
    screenshot = getattr(state, "screenshot", None)
    return screenshot_has_visible_content(screenshot)


def screenshot_has_visible_content(screenshot: object) -> bool:
    """Reject a nonempty but visually blank harness screenshot without persisting it."""

    if not isinstance(screenshot, str) or len(screenshot) < 100:
        return False
    try:
        from PIL import Image

        raw = base64.b64decode(screenshot, validate=True)
        with Image.open(io.BytesIO(raw)) as image:
            extrema = image.convert("L").resize((32, 32)).getextrema()
    except Exception:
        return False
    if not (
        isinstance(extrema, tuple)
        and len(extrema) == 2
        and isinstance(extrema[0], int)
        and isinstance(extrema[1], int)
    ):
        return False
    minimum, maximum = extrema
    return maximum - minimum >= 8


class BrowserUseRuntimeFailure(RuntimeError):
    """Content-free execution failure with a bounded startup/runtime stage."""

    def __init__(self, *, stage: str, cause_type: str) -> None:
        self.stage = stage
        self.cause_type = cause_type
        super().__init__("browser_use_runtime_failure")


class BrowserUseActionGuard:
    """Deny-oriented action policy without exact benign labels or routes."""

    @staticmethod
    def observable_url_rejection_reason(url: str) -> str | None:
        if not isinstance(url, str) or not 1 <= len(url) <= 4_000:
            return "url_bounds"
        try:
            parsed = urlsplit(url)
            port = parsed.port
        except ValueError:
            return "url_parse"
        host = (parsed.hostname or "").casefold().rstrip(".")
        if parsed.scheme.casefold() != "https":
            return "scheme"
        if parsed.username is not None or parsed.password is not None:
            return "credentials"
        if port not in (None, 443):
            return "port"
        if not (host == "booking.com" or host.endswith(".booking.com")):
            return "host"
        route = f"{parsed.path} {parsed.fragment}"
        query = parsed.query
        for _ in range(4):
            decoded = unquote(route)
            decoded_query = unquote(query)
            if decoded == route and decoded_query == query:
                break
            route = decoded
            query = decoded_query
        if len(route) > 4_000 or len(query) > 4_000:
            return "decoded_bounds"
        if _UNSAFE_ROUTE_TERMS.search(route) is not None:
            return "unsafe_route_term"
        try:
            query_items = parse_qsl(
                query,
                keep_blank_values=True,
                max_num_fields=200,
            )
        except ValueError:
            return "query_bounds"
        for key, value in query_items:
            normalized_key = key.strip().casefold()
            # Booking.com's search contract calls the non-mutating departure date
            # ``checkout``.  Do not confuse that exact ISO-date field with a checkout or
            # payment workflow elsewhere in a URL.
            if normalized_key == "checkout" and re.fullmatch(
                r"\d{4}-\d{2}-\d{2}", value.strip()
            ):
                continue
            if (
                _UNSAFE_QUERY_TERMS.search(key) is not None
                or _UNSAFE_QUERY_TERMS.search(value) is not None
            ):
                return "unsafe_query_term"
        return None

    @staticmethod
    def observable_url(url: str) -> bool:
        return BrowserUseActionGuard.observable_url_rejection_reason(url) is None

    def allows_click(
        self,
        *,
        current_url: str,
        label: str,
        role: str,
        attributes: Mapping[str, object],
    ) -> bool:
        return (
            self.click_rejection_reason(
                current_url=current_url,
                label=label,
                role=role,
                attributes=attributes,
            )
            is None
        )

    def click_rejection_reason(
        self,
        *,
        current_url: str,
        label: str,
        role: str,
        attributes: Mapping[str, object],
    ) -> str | None:
        if not self.observable_url(current_url):
            return "current_destination"
        if len(label) > 1_000 or len(role) > 100 or len(attributes) > 50:
            return "metadata_bounds"
        normalized_role = role.strip().casefold()
        if normalized_role in {"input", "select", "textarea", "option", "form"}:
            return "input_role"
        bounded_label = " ".join(label.split())
        if len(bounded_label) > 1_000:
            return "label_bounds"
        if UNSAFE_LABEL_TERMS.search(bounded_label):
            return "unsafe_label"
        normalized: dict[str, str] = {}
        for key, value in attributes.items():
            normalized_key = str(key).casefold()
            normalized_value = str(value)
            if len(normalized_key) > 100 or len(normalized_value) > 1_000:
                return "attribute_bounds"
            normalized[normalized_key] = normalized_value
        if normalized.get("type", "").casefold() in {"file", "password", "submit"}:
            return "unsafe_input_type"
        if any(key in normalized for key in ("download", "formaction", "contenteditable")):
            return "mutation_attribute"
        if any(key.startswith("on") for key in normalized):
            return "event_handler"
        if normalized.get("target", "").casefold() == "_blank":
            href = normalized.get("href")
            if not href or not self.observable_url(urljoin(current_url, href)):
                return "unsafe_new_tab_destination"
        if "disabled" in normalized or normalized.get("aria-disabled", "").casefold() == "true":
            return "disabled"
        # URL-bearing attributes are validated as destinations below. Treating their encoded
        # query text as a visible action label creates false positives for normal Booking.com
        # fields such as ``checkout=YYYY-MM-DD``. Presentational class/style values are likewise
        # implementation detail; continue scanning semantic and action-bearing metadata.
        attribute_text = " ".join(
            value
            for key, value in normalized.items()
            if key
            not in {
                "href",
                "src",
                "srcset",
                "action",
                "formaction",
                "class",
                "style",
            }
        )
        if len(attribute_text) > 4_000:
            return "attribute_text_bounds"
        if UNSAFE_LABEL_TERMS.search(attribute_text):
            return "unsafe_attribute_text"
        destinations = [
            normalized[key]
            for key in ("href", "src", "action", "formaction")
            if normalized.get(key)
        ]
        for destination in destinations:
            if not self.observable_url(urljoin(current_url, destination)):
                return "unsafe_destination"
        return None


def hardened_session_type(base: type[Any]) -> type[Any]:
    class HardenedBrowserSession(base):  # type: ignore[misc]
        async def attach_all_watchdogs(self) -> None:
            await super().attach_all_watchdogs()
            for handlers in self.event_bus.handlers.values():
                handlers[:] = [
                    handler
                    for handler in handlers
                    if not is_unsafe_watchdog_handler(handler)
                ]
            remaining = [
                handler
                for handlers in self.event_bus.handlers.values()
                for handler in handlers
                if is_unsafe_watchdog_handler(handler)
            ]
            if remaining:
                raise RuntimeError("unsafe Browser Use watchdog remained attached")

    return HardenedBrowserSession


class BrowserUseSessionStatus(Enum):
    TIMEOUT = "timeout"
    SIGNED_OUT = "signed_out"
    PROVIDER_FAILURE = "provider_failure"


@dataclass(frozen=True, slots=True)
class BrowserUseSession:
    browser: Any
    viewport: dict[str, int]
    file_system_dir: Path


class BrowserUseDeadlineRequest(Protocol):
    @property
    def limits(self) -> ExecutionLimits: ...


class BrowserUseSessionHost:
    """Own one confined Browser Use browser, session material, and transient files."""

    def __init__(self, mobile_settings: MobileWebSettings | None = None) -> None:
        self._mobile_settings = mobile_settings or MobileWebSettings()
        self._bootstrap = CodeOwnedSessionBootstrap()
        self._session: Any | None = None
        self._root: Path | None = None
        self._dialog_tasks: set[asyncio.Task[None]] = set()
        self._network_tasks: set[asyncio.Task[None]] = set()
        self._blocked_network_requests = 0
        self._blocked_network_hosts: set[str] = set()
        self._dialog_rejected = False
        self.verified_mobile_session: bytes | None = None
        self.failure_stage = "environment_prepare"

    @property
    def dialog_rejected(self) -> bool:
        return self._dialog_rejected

    @property
    def blocked_network_requests(self) -> int:
        return self._blocked_network_requests

    @property
    def blocked_network_hosts(self) -> frozenset[str]:
        return frozenset(self._blocked_network_hosts)

    def restore_session(self, data: bytes) -> None:
        self._bootstrap.restore_session(unexpired_cookie_material(data))

    async def start(self) -> BrowserUseSession:
        self.failure_stage = "environment_prepare"
        prepare_browser_use_environment()
        self.failure_stage = "dependency_check"
        try:
            installed_version = version("browser-use")
        except PackageNotFoundError as exc:
            raise RuntimeError("Browser Use 0.11.13 runtime is not installed") from exc
        if installed_version != "0.11.13":
            raise RuntimeError("Browser Use runtime differs from qualified version 0.11.13")
        try:
            from browser_use import BrowserProfile, BrowserSession
            from browser_use.browser.profile import ViewportSize
        except ImportError as exc:
            raise RuntimeError("Browser Use 0.11.13 runtime is not installed") from exc

        self.failure_stage = "transient_filesystem"
        self._root = Path(tempfile.mkdtemp(prefix="booksaver-browser-use-"))
        profile_dir = self._root / "browser-use-user-data-dir-profile"
        downloads_dir = self._root / "downloads"
        file_system_dir = self._root / "agent-files"
        for directory in (profile_dir, downloads_dir, file_system_dir, _CONFIG_DIR, _CACHE_DIR):
            directory.mkdir(parents=True, exist_ok=True)

        from playwright.async_api import async_playwright

        self.failure_stage = "playwright_probe"
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
        profile = BrowserProfile(
            executable_path=executable_path,
            headless=True,
            chromium_sandbox=False,
            user_data_dir=profile_dir,
            downloads_path=downloads_dir,
            accept_downloads=False,
            auto_download_pdfs=False,
            record_har_path=None,
            record_video_dir=None,
            traces_dir=None,
            storage_state=None,
            permissions=[],
            user_agent=str(mobile_options["user_agent"]),
            viewport=ViewportSize(
                width=int(viewport["width"]), height=int(viewport["height"])
            ),
            screen=ViewportSize(
                width=int(viewport["width"]), height=int(viewport["height"])
            ),
            device_scale_factor=float(mobile_options["device_scale_factor"]),
            allowed_domains=ALLOWED_DOMAINS,
            block_ip_addresses=True,
            keep_alive=False,
            enable_default_extensions=False,
            captcha_solver=False,
            highlight_elements=True,
            dom_highlight_elements=False,
            cross_origin_iframes=True,
        )
        self.failure_stage = "browser_session_start"
        session_type = hardened_session_type(BrowserSession)
        session = session_type(browser_profile=profile)
        self._session = session
        await session.start()
        actual_profile = Path(session.browser_profile.user_data_dir).resolve()
        assert self._root is not None
        if self._root.resolve() not in actual_profile.parents:
            raise RuntimeError("Browser Use profile escaped the BookSaver transient root")
        if session.cdp_url is None:
            raise RuntimeError("Browser Use did not expose local CDP")
        self.failure_stage = "mobile_emulation"
        await self._install_mobile_emulation(
            session,
            viewport=viewport,
            device_scale_factor=float(mobile_options["device_scale_factor"]),
            user_agent=str(mobile_options["user_agent"]),
            mobile=mobile_options["is_mobile"] is True,
        )
        await self._deny_downloads(session)
        await self._install_network_guard(session)
        await self._install_dialog_guard(session)
        self.failure_stage = "session_bootstrap"
        await self._bootstrap.apply(session.cdp_url)
        return BrowserUseSession(session, viewport, file_system_dir)

    async def _install_mobile_emulation(
        self,
        session: Any,
        *,
        viewport: Mapping[str, int],
        device_scale_factor: float,
        user_agent: str,
        mobile: bool = True,
    ) -> None:
        """Complete the device context options Browser Use's profile cannot express."""

        page_targets = session.get_page_targets()
        if len(page_targets) != 1:
            raise RuntimeError("Browser Use mobile emulation requires one page target")
        page_session = await session.get_or_create_cdp_session(
            page_targets[0].target_id,
            focus=False,
        )
        cdp = page_session.cdp_client
        session_id = page_session.session_id
        width = int(viewport["width"])
        height = int(viewport["height"])
        await cdp.send.Emulation.setDeviceMetricsOverride(
            params={
                "width": width,
                "height": height,
                "deviceScaleFactor": device_scale_factor,
                "mobile": mobile,
                "screenWidth": width,
                "screenHeight": height,
                "screenOrientation": {
                    "type": "portraitPrimary" if mobile else "landscapePrimary",
                    "angle": 0,
                },
            },
            session_id=session_id,
        )
        if mobile:
            await cdp.send.Emulation.setTouchEmulationEnabled(
                params={"enabled": True, "maxTouchPoints": 5},
                session_id=session_id,
            )
        await cdp.send.Emulation.setTimezoneOverride(
            params={"timezoneId": self._mobile_settings.timezone_id},
            session_id=session_id,
        )
        await cdp.send.Emulation.setLocaleOverride(
            params={"locale": self._mobile_settings.locale},
            session_id=session_id,
        )
        await cdp.send.Network.setUserAgentOverride(
            params={
                "userAgent": user_agent,
                "acceptLanguage": self._mobile_settings.locale,
                "platform": "Android" if mobile else "Win32",
            },
            session_id=session_id,
        )


    async def _deny_downloads(self, session: Any) -> None:
        await session.cdp_client.send.Browser.setDownloadBehavior(
            params={"behavior": "deny"}
        )

    async def verify_authentication(
        self,
        request: BrowserUseDeadlineRequest,
        browser_session: Any,
    ) -> BrowserUseSessionStatus | None:
        remaining = (request.limits.deadline - datetime.now(UTC)).total_seconds()
        if remaining <= 0:
            return BrowserUseSessionStatus.TIMEOUT
        try:
            verified = await asyncio.wait_for(
                self._verified_session_refresh(browser_session),
                timeout=min(remaining, 35.0),
            )
        except TimeoutError:
            return BrowserUseSessionStatus.TIMEOUT
        except Exception:
            return BrowserUseSessionStatus.PROVIDER_FAILURE
        if verified.outcome is SessionVerificationOutcome.AUTHENTICATED:
            if self.verified_mobile_session is None:
                self.verified_mobile_session = verified.cookies
            return None
        return (
            BrowserUseSessionStatus.SIGNED_OUT
            if verified.outcome is SessionVerificationOutcome.SIGNED_OUT
            else BrowserUseSessionStatus.PROVIDER_FAILURE
        )

    async def capture_verified_session(
        self,
        request: BrowserUseDeadlineRequest,
        browser_session: Any,
    ) -> bytes | None:
        remaining = (request.limits.deadline - datetime.now(UTC)).total_seconds()
        if remaining <= 0:
            return None
        try:
            verified = await asyncio.wait_for(
                self._verified_session_refresh(browser_session),
                timeout=min(remaining, 35.0),
            )
            return verified.cookies
        except Exception:
            return None

    async def _install_dialog_guard(self, session: Any) -> None:
        root = session._cdp_client_root
        if root is None:
            raise RuntimeError("Browser Use root CDP client is unavailable")

        page_targets = session.get_page_targets()
        if not page_targets:
            raise RuntimeError("Browser Use did not expose a page target for dialog guarding")
        for target in page_targets:
            page_session = await session.get_or_create_cdp_session(
                target.target_id,
                focus=False,
            )
            await page_session.cdp_client.send.Page.enable(
                session_id=page_session.session_id,
            )

            def reject_dialog(
                _event_data: Mapping[str, object],
                session_id: str | None = None,
                *,
                default_session_id: str = page_session.session_id,
            ) -> None:
                self._dialog_rejected = True

                async def dismiss() -> None:
                    try:
                        await root.send.Page.handleJavaScriptDialog(
                            params={"accept": False},
                            session_id=session_id or default_session_id,
                        )
                    except Exception:
                        pass

                # CDP awaits event handlers on its receive loop. Scheduling the reply avoids
                # deadlocking that loop while still rejecting every dialog immediately.
                task = asyncio.create_task(dismiss())
                self._dialog_tasks.add(task)
                task.add_done_callback(self._dialog_tasks.discard)

            page_session.cdp_client.register.Page.javascriptDialogOpening(reject_dialog)

    async def _install_network_guard(self, session: Any) -> None:
        root = session._cdp_client_root
        if root is None:
            raise RuntimeError("Browser Use root CDP client is unavailable")
        patterns = [{"urlPattern": "*", "requestStage": "Request"}]

        def track(operation: Any) -> None:
            async def bounded() -> None:
                try:
                    await operation
                except Exception:
                    pass

            task = asyncio.create_task(bounded())
            self._network_tasks.add(task)
            task.add_done_callback(self._network_tasks.discard)

        def request_paused(
            event_data: Mapping[str, object],
            session_id: str | None = None,
        ) -> None:
            request = event_data.get("request")
            request_id = event_data.get("requestId")
            url = request.get("url") if isinstance(request, Mapping) else None
            if not isinstance(request_id, str) or not isinstance(url, str):
                return
            if browser_request_allowed(url):
                track(
                    root.send.Fetch.continueRequest(
                        params={"requestId": request_id},
                        session_id=session_id,
                    )
                )
            else:
                self._blocked_network_requests += 1
                try:
                    blocked_host = (urlsplit(url).hostname or "").casefold().rstrip(".")
                except ValueError:
                    blocked_host = "invalid"
                if blocked_host and len(blocked_host) <= 255:
                    self._blocked_network_hosts.add(blocked_host)
                track(
                    root.send.Fetch.failRequest(
                        params={"requestId": request_id, "errorReason": "BlockedByClient"},
                        session_id=session_id,
                    )
                )

        async def enable(session_id: str) -> None:
            await root.send.Fetch.enable(
                params={"patterns": patterns},
                session_id=session_id,
            )

        root.register.Fetch.requestPaused(request_paused)
        for target in session.get_page_targets():
            page_session = await session.get_or_create_cdp_session(
                target.target_id,
                focus=False,
            )
            await enable(page_session.session_id)

        def target_attached(
            event_data: Mapping[str, object],
            _session_id: str | None = None,
        ) -> None:
            attached_session_id = event_data.get("sessionId")
            target_info = event_data.get("targetInfo")
            target_type = (
                target_info.get("type") if isinstance(target_info, Mapping) else None
            )
            if isinstance(attached_session_id, str) and target_type in {
                "page",
                "iframe",
                "worker",
                "shared_worker",
                "service_worker",
            }:
                track(enable(attached_session_id))

        root.register.Target.attachedToTarget(target_attached)

    async def _verified_session_refresh(
        self,
        browser_session: Any,
    ) -> SessionVerificationResult:
        from playwright.async_api import async_playwright

        playwright = await async_playwright().start()
        try:
            browser = await playwright.chromium.connect_over_cdp(browser_session.cdp_url)
            if len(browser.contexts) != 1:
                return SessionVerificationResult(SessionVerificationOutcome.RETRY_LATER)
            context = browser.contexts[0]
            if len(context.pages) != 1:
                return SessionVerificationResult(SessionVerificationOutcome.RETRY_LATER)
            for settle_milliseconds in _ACCOUNT_AUTH_SETTLE_MILLISECONDS:
                await browser_session.navigate_to(ACCOUNT_PROBE_URL, new_tab=False)
                await asyncio.sleep(settle_milliseconds / 1_000)
            serialized = json.dumps(
                await context.cookies(),
                ensure_ascii=True,
                separators=(",", ":"),
                sort_keys=True,
            ).encode("utf-8")
            CodeOwnedSessionBootstrap._decode_cookies(serialized)
            descriptor = playwright.devices[self._mobile_settings.profile.playwright_device_name]
            options = self._mobile_settings.context_options(descriptor)
            options.update(accept_downloads=False, service_workers="block")
            return await verify_saved_snapshot(
                browser, options, serialized, time.monotonic() + 27.0,
            )
        finally:
            await playwright.stop()

    async def close(self) -> None:
        self.verified_mobile_session = None
        if self._network_tasks:
            await asyncio.gather(*tuple(self._network_tasks), return_exceptions=True)
            self._network_tasks.clear()
        if self._dialog_tasks:
            await asyncio.gather(*tuple(self._dialog_tasks), return_exceptions=True)
            self._dialog_tasks.clear()
        session, self._session = self._session, None
        if session is not None:
            try:
                if session.is_cdp_connected:
                    await session.kill()
            except Exception:
                logger.warning("Browser Use transient browser cleanup failed", exc_info=False)
        paths = [self._root]
        self._root = None
        temp_root = Path(tempfile.gettempdir()).resolve()
        for path in paths:
            if path is None:
                continue
            try:
                resolved = path.resolve()
                if resolved.parent == temp_root or temp_root in resolved.parents:
                    await asyncio.to_thread(shutil.rmtree, resolved, True)
            except Exception:
                logger.warning("Browser Use transient file cleanup failed", exc_info=False)
