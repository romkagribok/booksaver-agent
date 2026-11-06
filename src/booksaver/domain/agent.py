from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING
from urllib.parse import urljoin, urlsplit

from .check_result import FailureCode

if TYPE_CHECKING:
    from .browser_resilience import TerminalBrowserDiagnosis
    from .model_policy import ModelStopReason


class AgentActionType(Enum):
    """The complete action vocabulary (ADR-016) — nothing else reaches the browser."""

    CLICK = "click"
    FILL = "fill"
    SELECT = "select"
    SCROLL = "scroll"
    EXTRACT = "extract"
    REQUEST_SCREENSHOT = "request_screenshot"
    GIVE_UP = "give_up"


class AgentStopReason(Enum):
    """Stable terminal reasons supplied by a model or the recovery controller."""

    CAPTCHA = "captcha"
    AUTHENTICATION_REQUIRED = "authentication_required"
    EXPLICIT_UNAVAILABLE = "explicit_unavailable"
    UNSAFE_ACTION = "unsafe_action"
    MISSING_BROWSER_CAPABILITY = "missing_browser_capability"
    NO_PROGRESS = "no_progress"
    PROVIDER_ERROR = "provider_error"
    BUDGET_EXHAUSTED = "budget_exhausted"
    UNKNOWN = "unknown"


class AgentDiagnosisReason(Enum):
    """Advisory, content-free DOM diagnosis allowed on an actionless stop."""

    UNSUPPORTED_PAGE = "unsupported_page"
    UNRESOLVED_AMBIGUITY = "unresolved_ambiguity"
    CODE_MAINTENANCE_REQUIRED = "code_maintenance_required"


@dataclass(frozen=True)
class LLMUsage:
    """Provider-neutral token usage for one completed model call."""

    input_tokens: int = 0
    output_tokens: int = 0

    def __post_init__(self) -> None:
        if self.input_tokens < 0 or self.output_tokens < 0:
            raise ValueError("LLM token usage cannot be negative")

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


@dataclass(frozen=True)
class AgentAction:
    type: AgentActionType
    ref: str | None = None  # element reference from the current observation
    value: str | None = None  # fill/select text, scroll direction, or give-up reason
    stop_reason: AgentStopReason | None = None
    diagnosis_reason: AgentDiagnosisReason | None = None
    diagnosis_confidence: float | None = None

    def __post_init__(self) -> None:
        if self.diagnosis_reason is not None and self.type is not AgentActionType.GIVE_UP:
            raise ValueError("only an actionless give_up may carry a diagnosis")
        if self.diagnosis_confidence is not None:
            if self.diagnosis_reason is None:
                raise ValueError("diagnosis confidence requires a typed diagnosis")
            if isinstance(self.diagnosis_confidence, bool) or not (
                0.0 <= self.diagnosis_confidence <= 1.0
            ):
                raise ValueError("diagnosis confidence must be between zero and one")


@dataclass(frozen=True)
class ElementInfo:
    ref: str  # e.g. "e7"; valid only for the observation that produced it
    role: str  # link | button | input | select
    label: str
    href: str | None = None


@dataclass(frozen=True)
class Observation:
    """What the agent sees this turn. Tier 1 is text + elements; tier 2 adds a
    screenshot (ADR-015)."""

    url: str
    title: str
    text: str
    elements: tuple[ElementInfo, ...]
    screenshot: bytes | None = None
    # Metadata is deliberately defaulted so existing browser adapters remain
    # source-compatible while popup-aware adapters are introduced.
    popup_count: int = 0
    popup_urls: tuple[str, ...] = ()
    scroll_y: int = 0

    def describe(self, max_text_chars: int = 30_000) -> str:
        lines = [f"URL: {self.url}", f"Title: {self.title}", "", "Interactive elements:"]
        for el in self.elements:
            href = f" href={el.href}" if el.href else ""
            lines.append(f"  [{el.ref}] {el.role}: {el.label!r}{href}")
        lines += ["", "Visible page text:", self.text[:max_text_chars]]
        return "\n".join(lines)


@dataclass(frozen=True)
class RecoveryPolicy:
    """Tight per-step bounds layered underneath the shared per-check budget."""

    max_llm_calls: int = 4
    timeout_seconds: int = 60
    no_progress_before_screenshot: int = 2
    max_semantic_executions: int = 2

    def __post_init__(self) -> None:
        for name in (
            "max_llm_calls",
            "timeout_seconds",
            "no_progress_before_screenshot",
            "max_semantic_executions",
        ):
            if getattr(self, name) < 1:
                raise ValueError(f"recovery.{name} must be >= 1")


class AgentHistoryOutcome(Enum):
    SCRIPT_FAILED = "script_failed"
    SCREENSHOT_REQUESTED = "screenshot_requested"
    EXECUTED = "executed"
    FAILED = "failed"
    REFUSED = "refused"
    STOPPED = "stopped"


@dataclass(frozen=True)
class AgentHistoryEvent:
    """Provider-neutral facts from one recovery operation."""

    outcome: AgentHistoryOutcome
    detail: str
    action: AgentAction | None = None
    semantic_target: str | None = None
    goal_verified: bool = False
    url_changed: bool = False
    content_changed: bool = False
    elements_changed: bool = False
    scroll_changed: bool = False
    popup_opened: bool = False
    error: str | None = None

    @property
    def made_progress(self) -> bool:
        return self.goal_verified or any(
            (
                self.url_changed,
                self.content_changed,
                self.elements_changed,
                self.scroll_changed,
            )
        )


@dataclass(frozen=True)
class AgentTurnContext:
    """Complete input for one provider-neutral browser-agent decision."""

    goal: str
    observation: Observation
    history: tuple[AgentHistoryEvent, ...]
    llm_calls_used: int
    max_llm_calls: int
    no_progress_count: int
    screenshot_forced: bool = False
    seconds_remaining: float | None = None
    verification_condition: str | None = None
    terminal_diagnosis_required: bool = False


@dataclass(frozen=True)
class AgentSettings:
    """The per-job cost cap that bounds Jev price and sync execution (ADR-017)."""

    max_job_cost_micro_usd: int = 1_000_000

    def __post_init__(self) -> None:
        if not 1 <= self.max_job_cost_micro_usd <= 1_000_000:
            raise ValueError("agent.max_job_cost_usd must be between 0.000001 and 1.00")


# ── Action guard (ADR-016): enforced at the adapter boundary, never prompt-only ──

_BLOCKED_LABEL = re.compile(
    r"(reserve|book now|i'?ll reserve|confirm (booking|reservation)|pay now|"
    r"complete (booking|purchase)|cancel (booking|reservation)|confirm cancellation|"
    r"(?:modify|edit|change|update|remove|delete)\s+(?:a\s+|the\s+|your\s+)?"
    r"(?:booking|reservation|stay|guest|room|dates?|payment|account)|"
    r"save\s+(?:changes?|booking|reservation|account))",
    re.IGNORECASE,
)
_BLOCKED_URL = re.compile(
    r"(secure\.booking\.com/book|/book\.html|/cancel|/payments?\b|/checkout|"
    r"/orders/(?:create|confirm|submit)|"
    r"/(?:bookings?|reservations?)/(?:modify|edit|cancel)|"
    r"/account/(?:settings|security))",
    re.IGNORECASE,
)


def blocked_action_reason(action: AgentAction, observation: Observation) -> str | None:
    """Reason the action must be refused, or None if it is safe."""
    if action.type not in (AgentActionType.CLICK, AgentActionType.FILL, AgentActionType.SELECT):
        return None
    element = next((el for el in observation.elements if el.ref == action.ref), None)
    if element is None:
        return None  # unknown ref is handled as a failed action, not a guard block
    if _BLOCKED_LABEL.search(element.label):
        return "target label is reservation-mutating"
    if element.href and _BLOCKED_URL.search(element.href):
        return "target destination is reservation-mutating"
    if element.href:
        destination = urlsplit(urljoin(observation.url, element.href))
        hostname = (destination.hostname or "").lower().rstrip(".")
        if (
            destination.scheme.lower() != "https"
            or not hostname
            or not (hostname == "booking.com" or hostname.endswith(".booking.com"))
        ):
            return "target href leaves the approved Booking.com web origin"
    return None


def blocked_url_reason(url: str) -> str | None:
    """Reason the current URL means the check must stop, or None."""
    if _BLOCKED_URL.search(url):
        return "navigated into a reservation-mutating flow"
    return None


# ── Escalation result + trace records ─────────────────────────────────────────


@dataclass(frozen=True)
class EscalationResult:
    ok: bool
    detail: str
    failure_code: FailureCode | None = None
    used_screenshot: bool = False
    stop_reason: AgentStopReason | None = None
    model_stop_reason: ModelStopReason | None = None
    diagnosis: TerminalBrowserDiagnosis | None = None


class TraceKind(Enum):
    JOURNEY_STEP = "journey_step"
    CURRENCY_ALIGNMENT = "currency_alignment"
    ESCALATION_STARTED = "escalation_started"
    AGENT_ACTION = "agent_action"
    AGENT_OUTCOME = "agent_outcome"
    AGENT_BLOCKED = "agent_blocked"
    SCREENSHOT_TIER = "screenshot_tier"
    AGENT_RESULT = "agent_result"
    CHECK_RESULT = "check_result"
    PRICE_SOURCE = "price_source"
    PRICE_VALIDATION = "price_validation"


@dataclass(frozen=True)
class TraceEvent:
    seq: int
    at: datetime
    kind: TraceKind
    detail: str


@dataclass(frozen=True)
class CheckTrace:
    check_id: str
    booking_id: str
    created_at: datetime
    events: tuple[TraceEvent, ...] = field(default_factory=tuple)
