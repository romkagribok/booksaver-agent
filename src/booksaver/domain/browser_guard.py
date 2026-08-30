"""Provider-neutral safety policy for read-only agentic browser actions."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from urllib.parse import urlsplit


class BrowserActionType(Enum):
    CLICK = "click"
    SCROLL = "scroll"
    TYPE = "type"
    KEY = "key"
    WAIT = "wait"
    ZOOM = "zoom"


class ExecutorEgressKind(Enum):
    BOOKING = "booking"
    ANTHROPIC = "anthropic"
    LOOPBACK = "loopback"


class GuardRejection(Enum):
    UNSUPPORTED_ACTION = "unsupported_action"
    INVALID_DESTINATION = "invalid_destination"
    UNEXPECTED_POPUP = "unexpected_popup"
    UNSAFE_LABEL = "unsafe_label"
    UNSAFE_PATH = "unsafe_path"
    UNSAFE_INPUT = "unsafe_input"
    INVALID_COORDINATE = "invalid_coordinate"
    TARGET_NOT_ACTIONABLE = "target_not_actionable"
    UNSAFE_KEY = "unsafe_key"
    UNSAFE_SCROLL = "unsafe_scroll"
    UNSAFE_WAIT = "unsafe_wait"
    UNSAFE_ZOOM = "unsafe_zoom"


@dataclass(frozen=True, slots=True)
class DestinationSnapshot:
    url: str
    popup_count: int = 0

    def __post_init__(self) -> None:
        if not self.url.strip() or len(self.url) > 2_000:
            raise ValueError("destination URL must be bounded and non-empty")
        if isinstance(self.popup_count, bool) or self.popup_count < 0:
            raise ValueError("popup_count must be non-negative")


@dataclass(frozen=True, slots=True)
class CoordinateHitTest:
    x: int
    y: int
    viewport_width: int
    viewport_height: int
    label: str = ""
    role: str = ""
    href: str | None = None
    visible: bool = True
    enabled: bool = True

    @property
    def in_viewport(self) -> bool:
        return 0 <= self.x < self.viewport_width and 0 <= self.y < self.viewport_height


@dataclass(frozen=True, slots=True)
class BrowserActionProposal:
    action: BrowserActionType
    current: DestinationSnapshot
    label: str = ""
    role: str = ""
    destination: str | None = None
    value: str | None = None
    x: int | None = None
    y: int | None = None
    delta_x: int = 0
    delta_y: int = 0
    wait_ms: int | None = None
    zoom_region: tuple[int, int, int, int] | None = None
    viewport_width: int | None = None
    viewport_height: int | None = None
    hit_test: CoordinateHitTest | None = None


@dataclass(frozen=True, slots=True)
class GuardDecision:
    allowed: bool
    rejection: GuardRejection | None = None

    def __post_init__(self) -> None:
        if self.allowed == (self.rejection is not None):
            raise ValueError("guard decision must be allowed or contain one rejection")


_UNSAFE_TEXT = re.compile(
    r"\b(reserve|reservation|book(?:\s+now)?|pay|payment|purchase|buy|checkout|"
    r"cancel|delete|remove|change\s+(?:booking|reservation)|confirm\s+(?:booking|"
    r"reservation|payment)|sign\s*in|log\s*in|password|passcode|verification\s*code|"
    r"captcha|mfa|two[- ]factor|upload|download|my\s+account|profile|account\s+settings|"
    r"accept\s+(?:all\s+)?cookies|agree\s+(?:and\s+continue)?|consent)\b",
    re.IGNORECASE,
)
_UNSAFE_PATH = re.compile(
    r"/(?:book|booking|checkout|payment|pay|purchase|cancel|manage-booking|"
    r"reservation|auth|login|signin|myaccount|my-bookings|profile|settings)(?:\.html)?(?:/|$)",
    re.IGNORECASE,
)
_SAFE_KEYS = frozenset(
    {
        "ARROWDOWN",
        "ARROWUP",
        "ARROWLEFT",
        "ARROWRIGHT",
        "PAGEDOWN",
        "PAGEUP",
        "HOME",
        "END",
        "ESCAPE",
        "TAB",
        "SHIFT+TAB",
    }
)


def is_booking_destination(url: str) -> bool:
    """Accept only normal HTTPS Booking.com pages, never embedded credentials/ports."""
    try:
        parsed = urlsplit(url)
        host = (parsed.hostname or "").casefold().rstrip(".")
        port = parsed.port
    except ValueError:
        return False
    return (
        parsed.scheme.casefold() == "https"
        and parsed.username is None
        and parsed.password is None
        and port in {None, 443}
        and (host == "booking.com" or host.endswith(".booking.com"))
    )


def classify_executor_egress(url: str) -> ExecutorEgressKind | None:
    """Classify the complete network allowlist for an authenticated executor run."""
    try:
        parsed = urlsplit(url)
        host = (parsed.hostname or "").casefold().rstrip(".")
        port = parsed.port
    except ValueError:
        return None
    if parsed.username is not None or parsed.password is not None:
        return None
    if is_booking_destination(url):
        return ExecutorEgressKind.BOOKING
    if (
        parsed.scheme.casefold() == "https"
        and port in {None, 443}
        and (host == "bstatic.com" or host.endswith(".bstatic.com"))
    ):
        # Booking.com serves the page's own scripts, styles, and images from bstatic.com.
        # This is page-delivery egress only; it is never an approved top-level destination.
        return ExecutorEgressKind.BOOKING
    if (
        parsed.scheme.casefold() == "https"
        and host == "api.anthropic.com"
        and port in {None, 443}
    ):
        return ExecutorEgressKind.ANTHROPIC
    if (
        parsed.scheme.casefold() in {"http", "https", "ws", "wss"}
        and host in {"127.0.0.1", "localhost", "::1"}
    ):
        return ExecutorEgressKind.LOOPBACK
    return None


def _unsafe_destination(url: str | None) -> GuardRejection | None:
    if url is None:
        return None
    if not is_booking_destination(url):
        return GuardRejection.INVALID_DESTINATION
    if _UNSAFE_PATH.search(urlsplit(url).path):
        return GuardRejection.UNSAFE_PATH
    return None


class BrowserActionGuard:
    """Fail-closed guard shared by semantic replay and computer-use actions."""

    def evaluate(self, proposal: BrowserActionProposal) -> GuardDecision:
        rejection = self._rejection(proposal)
        return GuardDecision(rejection is None, rejection)

    def validate_destination(
        self,
        before: DestinationSnapshot,
        after: DestinationSnapshot,
    ) -> GuardDecision:
        if after.popup_count > before.popup_count:
            return GuardDecision(False, GuardRejection.UNEXPECTED_POPUP)
        rejection = _unsafe_destination(after.url)
        return GuardDecision(rejection is None, rejection)

    def _rejection(self, proposal: BrowserActionProposal) -> GuardRejection | None:
        if proposal.current.popup_count:
            return GuardRejection.UNEXPECTED_POPUP
        destination_rejection = _unsafe_destination(proposal.current.url)
        if destination_rejection is not None:
            return destination_rejection
        destination_rejection = _unsafe_destination(proposal.destination)
        if destination_rejection is not None:
            return destination_rejection
        if _UNSAFE_TEXT.search(f"{proposal.role} {proposal.label}"):
            return GuardRejection.UNSAFE_LABEL

        if proposal.action is BrowserActionType.CLICK:
            return self._click_rejection(proposal)
        if proposal.action is BrowserActionType.SCROLL:
            if proposal.delta_x != 0 or not 0 < abs(proposal.delta_y) <= 1_200:
                return GuardRejection.UNSAFE_SCROLL
            return None
        if proposal.action is BrowserActionType.TYPE:
            if (
                proposal.value is None
                or not proposal.value
                or len(proposal.value) > 300
                or _UNSAFE_TEXT.search(proposal.value)
            ):
                return GuardRejection.UNSAFE_INPUT
            if proposal.role.casefold() not in {"textbox", "searchbox", "combobox", "input"}:
                return GuardRejection.UNSAFE_INPUT
            return None
        if proposal.action is BrowserActionType.KEY:
            if proposal.value is None or proposal.value.upper() not in _SAFE_KEYS:
                return GuardRejection.UNSAFE_KEY
            return None
        if proposal.action is BrowserActionType.WAIT:
            if proposal.wait_ms is None or not 1 <= proposal.wait_ms <= 5_000:
                return GuardRejection.UNSAFE_WAIT
            return None
        if proposal.action is BrowserActionType.ZOOM:
            region = proposal.zoom_region
            if (
                region is None
                or proposal.viewport_width is None
                or proposal.viewport_height is None
            ):
                return GuardRejection.UNSAFE_ZOOM
            x0, y0, x1, y1 = region
            if not (
                0 <= x0 < x1 <= proposal.viewport_width
                and 0 <= y0 < y1 <= proposal.viewport_height
                and x1 - x0 >= 10
                and y1 - y0 >= 10
            ):
                return GuardRejection.UNSAFE_ZOOM
            return None
        return GuardRejection.UNSUPPORTED_ACTION

    @staticmethod
    def _click_rejection(proposal: BrowserActionProposal) -> GuardRejection | None:
        hit = proposal.hit_test
        if hit is None:
            # Semantic actions are inspected through their selector instead of coordinates.
            if proposal.x is not None or proposal.y is not None:
                return GuardRejection.INVALID_COORDINATE
            return None
        if not hit.in_viewport or proposal.x != hit.x or proposal.y != hit.y:
            return GuardRejection.INVALID_COORDINATE
        if not hit.visible or not hit.enabled:
            return GuardRejection.TARGET_NOT_ACTIONABLE
        if _UNSAFE_TEXT.search(f"{hit.role} {hit.label}"):
            return GuardRejection.UNSAFE_LABEL
        return _unsafe_destination(hit.href)
