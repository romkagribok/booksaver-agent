from __future__ import annotations

import re
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from .check_result import FailureCode


class AgentActionType(Enum):
    """The complete action vocabulary (ADR-016) — nothing else reaches the browser."""

    CLICK = "click"
    FILL = "fill"
    SELECT = "select"
    SCROLL = "scroll"
    EXTRACT = "extract"
    REQUEST_SCREENSHOT = "request_screenshot"
    GIVE_UP = "give_up"


@dataclass(frozen=True)
class AgentAction:
    type: AgentActionType
    ref: str | None = None  # element reference from the current observation
    value: str | None = None  # fill/select text, scroll direction, or give-up reason


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

    def describe(self, max_text_chars: int = 30_000) -> str:
        lines = [f"URL: {self.url}", f"Title: {self.title}", "", "Interactive elements:"]
        for el in self.elements:
            href = f" href={el.href}" if el.href else ""
            lines.append(f"  [{el.ref}] {el.role}: {el.label!r}{href}")
        lines += ["", "Visible page text:", self.text[:max_text_chars]]
        return "\n".join(lines)


@dataclass(frozen=True)
class AgentSettings:
    """Hard per-check cost caps (ADR-017). Deliberately simple: if these prove too
    blunt, the named future work is adaptive budgeting (per-day budgets, backoff,
    model downshift) — see adr-017 and README."""

    max_steps: int = 15
    max_llm_calls: int = 20
    check_timeout_seconds: int = 180
    model: str = "claude-sonnet-4-6"

    def __post_init__(self) -> None:
        if self.max_steps < 1:
            raise ValueError(f"agent.max_steps must be >= 1, got {self.max_steps}")
        if self.max_llm_calls < 1:
            raise ValueError(f"agent.max_llm_calls must be >= 1, got {self.max_llm_calls}")
        if not 30 <= self.check_timeout_seconds <= 3600:
            raise ValueError(
                "agent.check_timeout_seconds must be between 30 and 3600, "
                f"got {self.check_timeout_seconds}"
            )


class BudgetExceeded(Exception):
    """Raised the moment any hard cap is breached; maps to BUDGET_EXCEEDED."""


class AgentBudget:
    """Mutable per-check budget. Screenshot (tier-2) turns cost 2 steps (ADR-015)."""

    def __init__(
        self, settings: AgentSettings, clock: Callable[[], float] = time.monotonic
    ) -> None:
        self._settings = settings
        self._clock = clock
        self._started = clock()
        self.steps_used = 0
        self.llm_calls_used = 0

    def consume_step(self, tier2: bool = False) -> None:
        self.steps_used += 2 if tier2 else 1
        if self.steps_used > self._settings.max_steps:
            raise BudgetExceeded(
                f"agent step cap exceeded ({self.steps_used}/{self._settings.max_steps})"
            )

    def consume_llm_call(self) -> None:
        if self.llm_calls_used >= self._settings.max_llm_calls:
            raise BudgetExceeded(
                f"LLM call cap exceeded "
                f"({self.llm_calls_used}/{self._settings.max_llm_calls})"
            )
        self.llm_calls_used += 1

    def check_time(self) -> None:
        elapsed = self._clock() - self._started
        if elapsed > self._settings.check_timeout_seconds:
            raise BudgetExceeded(
                f"check timeout exceeded ({elapsed:.0f}s/"
                f"{self._settings.check_timeout_seconds}s)"
            )


# ── Action guard (ADR-016): enforced at the adapter boundary, never prompt-only ──

_BLOCKED_LABEL = re.compile(
    r"(reserve|book now|i'?ll reserve|confirm (booking|reservation)|pay now|"
    r"complete (booking|purchase)|cancel (booking|reservation)|confirm cancellation)",
    re.IGNORECASE,
)
_BLOCKED_URL = re.compile(
    r"(secure\.booking\.com/book|/book\.html|/cancel|/payments?\b|/checkout)",
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
        return f"target label {element.label!r} is reservation-mutating"
    if element.href and _BLOCKED_URL.search(element.href):
        return f"target href {element.href!r} is reservation-mutating"
    return None


def blocked_url_reason(url: str) -> str | None:
    """Reason the current URL means the check must stop, or None."""
    if _BLOCKED_URL.search(url):
        return f"navigated into a reservation-mutating flow: {url}"
    return None


# ── Escalation result + trace records ─────────────────────────────────────────


@dataclass(frozen=True)
class EscalationResult:
    ok: bool
    detail: str
    failure_code: FailureCode | None = None  # AGENT_GAVE_UP / BLOCKED_ACTION / BUDGET_EXCEEDED
    used_screenshot: bool = False


class TraceKind(Enum):
    JOURNEY_STEP = "journey_step"
    CURRENCY_ALIGNMENT = "currency_alignment"
    ESCALATION_STARTED = "escalation_started"
    AGENT_ACTION = "agent_action"
    AGENT_BLOCKED = "agent_blocked"
    SCREENSHOT_TIER = "screenshot_tier"
    AGENT_RESULT = "agent_result"
    CHECK_RESULT = "check_result"
    PRICE_SOURCE = "price_source"


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
