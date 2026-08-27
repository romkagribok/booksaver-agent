"""Local Stagehand inventory executor with guarded Anthropic computer-use fallback.

The adapter is deliberately positive-only.  It can return visible reservation evidence and
diagnostic traversal coverage, but it cannot claim account completeness or authorize absence.
Provider/browser objects and content-bearing evidence remain inside this module.
"""

from __future__ import annotations

import asyncio
import base64
import logging
import re
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import UTC, date, datetime
from decimal import InvalidOperation
from enum import Enum
from typing import Any, Protocol, cast
from urllib.parse import SplitResult, parse_qs, parse_qsl, unquote, urlsplit

from booksaver.application.async_runner import AsyncLoopRunner
from booksaver.application.browser_executor import ExecutionMeter, InMemorySessionLeaseBroker
from booksaver.application.model_policy import AdmittedModelAttempt, BrowserJobCostBudget
from booksaver.application.ports import SessionRestoreTarget
from booksaver.domain.account_sync import ReservationLifecycle
from booksaver.domain.agent import LLMUsage
from booksaver.domain.browser_executor import (
    AllInEvidence,
    EvidenceCompleteness,
    ExecutionUsage,
    ExecutorSafetyViolation,
    ObservationSource,
    RedactedProvenance,
    RefundabilityEvidence,
)
from booksaver.domain.browser_guard import (
    BrowserActionProposal,
    BrowserActionType,
    CoordinateHitTest,
    DestinationSnapshot,
    ExecutorEgressKind,
    GuardDecision,
    GuardRejection,
    classify_executor_egress,
    is_booking_destination,
)
from booksaver.domain.inventory_executor import (
    InventoryExecutionRequest,
    InventoryExecutionResult,
    InventoryExecutionStatus,
    InventoryScope,
    ObservedInventoryScope,
    ObservedReservation,
)
from booksaver.domain.model_policy import (
    AdaptiveModelPortfolio,
    EscalationTrigger,
    ModelAttemptOutcome,
    ModelAttemptPlan,
    ModelRole,
    TokenEnvelope,
)
from booksaver.domain.value_objects import Money, Occupancy
from booksaver.infrastructure.browser.agentic_executor import (
    ComputerActionRequest,
    InspectedElement,
    LocalStagehandRuntime,
    ProviderUsage,
    SemanticAction,
    _parse_computer_action,
    _stagehand_usage,
)

logger = logging.getLogger(__name__)

INVENTORY_ENTRY_URL = "https://secure.booking.com/myreservations.html"
_ANTHROPIC_API_BASE = "https://api.anthropic.com"
_ANTHROPIC_MODEL = "claude-sonnet-5"
_COMPUTER_USE_BETA = "computer-use-2025-11-24"
_VIEWPORT_WIDTH = 1280
_VIEWPORT_HEIGHT = 800
_MODEL_ENVELOPE = TokenEnvelope(30_000, 4_096)
_MAX_SCOPE_PAGES = 20
_MAX_DETAIL_TASKS = 20
_CONFIRMATION_QUERY_KEYS = frozenset({"trip_id", "reservation_id"})

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
_CANONICAL_SAFE_KEYS = {
    "ARROWDOWN": "ArrowDown",
    "ARROWUP": "ArrowUp",
    "ARROWLEFT": "ArrowLeft",
    "ARROWRIGHT": "ArrowRight",
    "PAGEDOWN": "PageDown",
    "PAGEUP": "PageUp",
    "HOME": "Home",
    "END": "End",
    "ESCAPE": "Escape",
    "TAB": "Tab",
    "SHIFT+TAB": "Shift+Tab",
}
_UNSAFE_INVENTORY_TEXT = re.compile(
    r"\b(book\s+now|reserve\s+now|pay|payment|purchase|buy|checkout|cancel|delete|"
    r"remove|change\s+(?:booking|reservation)|modify\s+(?:booking|reservation)|"
    r"edit\s+(?:booking|reservation|dates?)|change\s+(?:dates?|rooms?|guests?)|"
    r"modify\s+(?:dates?|rooms?|guests?)|upgrade|add\s+extras?|"
    r"confirm\s+(?:booking|reservation|payment)|"
    r"sign\s*in|log\s*in|password|passcode|verification\s*code|captcha|mfa|"
    r"two[- ]factor|upload|download|account\s+settings|profile|"
    r"accept\s+(?:all\s+)?cookies|agree(?:\s+and\s+continue)?|consent)\b",
    re.IGNORECASE,
)
_PAGINATION_TEXT = re.compile(
    r"\b(next\s+(?:page|reservations?|bookings?|trips?|stays?)|"
    r"(?:show|load)\s+more(?:\s+(?:reservations?|bookings?|trips?|stays?))?|"
    r"(?:older|newer)\s+(?:reservations?|bookings?|trips?|stays?))\b",
    re.IGNORECASE,
)
_DETAIL_TEXT = re.compile(
    r"\b(view|open|show)\s+(?:reservation|booking|trip|confirmation)?\s*details?\b|"
    r"\b(?:reservation|booking|trip|confirmation)\s+details?\b",
    re.IGNORECASE,
)
_SCOPE_ALIASES: dict[InventoryScope, frozenset[str]] = {
    InventoryScope.UPCOMING: frozenset({"upcoming", "active", "confirmed"}),
    InventoryScope.PAST: frozenset({"past", "previous", "completed"}),
    InventoryScope.CANCELLED: frozenset({"cancelled", "canceled"}),
}

_AUTH_DESTINATION_TEXT = re.compile(
    r"\b(sign\s*in|signin|log\s*in|login|auth|password|passcode|two[- ]factor|mfa)\b",
    re.IGNORECASE,
)
_CHALLENGE_DESTINATION_TEXT = re.compile(
    r"\b(captcha|verify\s*human|challenge|bot\s*wall)\b", re.IGNORECASE
)
_MUTATION_DESTINATION_TEXT = re.compile(
    r"\b(book\s+now|reserve\s+now|pay|payment|purchase|buy|checkout|cancel|delete|"
    r"remove|change|modify|edit|manage|upgrade|extras?|upload|download|account\s+settings|"
    r"profile)\b",
    re.IGNORECASE,
)
_MUTATION_PATH_TEXT = re.compile(r"\b(book|reserve)\b", re.IGNORECASE)
_INVENTORY_DESTINATION_TEXT = re.compile(
    r"\b(my\s*reservations?|my\s*trips?|reservations?|bookings?|trips?|stays?)\b",
    re.IGNORECASE,
)
_CONFIRMATION_DESTINATION_TEXT = re.compile(
    r"\b(confirmation|reservation\s*details?|booking\s*details?|trip\s*details?)\b",
    re.IGNORECASE,
)
_SAFE_LOG_QUERY_KEY = re.compile(r"^[a-z][a-z0-9_.-]{0,31}$")
_SAFE_LOG_PATH_COMPONENTS = frozenset(
    {
        "account",
        "auth",
        "booking",
        "bookings",
        "captcha",
        "challenge",
        "confirmation",
        "confirmation.html",
        "detail",
        "details",
        "login",
        "my-reservations",
        "my-trips",
        "myreservations",
        "myreservations.html",
        "mytrips",
        "mytrips.html",
        "reservation",
        "reservations",
        "sign-in",
        "signin",
        "stay",
        "stays",
        "trip",
        "trips",
        "verify-human",
    }
)


class DestinationDisposition(Enum):
    DENY = "deny"
    OBSERVE_ONLY = "observe_only"
    INTERACT = "interact"


class DestinationCategory(Enum):
    INVENTORY = "inventory"
    CONFIRMATION = "confirmation"
    AUTHENTICATION = "authentication"
    CHALLENGE = "challenge"
    MUTATION = "mutation"
    UNKNOWN_BOOKING = "unknown_booking"
    EXTERNAL = "external"
    INVALID = "invalid"


@dataclass(frozen=True, slots=True)
class DestinationAssessment:
    disposition: DestinationDisposition
    category: DestinationCategory
    host_class: str
    path_template: str
    query_keys: tuple[str, ...]
    fragment_present: bool
    terminal_status: InventoryExecutionStatus | None = None


class InventoryTaskKind(Enum):
    SCOPE = "scope"
    PAGINATION = "pagination"
    DETAIL = "detail"


@dataclass(frozen=True, slots=True)
class InventoryTraversalTask:
    kind: InventoryTaskKind
    scope: InventoryScope
    remote_id: str | None = None

    def __post_init__(self) -> None:
        if self.kind is InventoryTaskKind.DETAIL:
            if self.remote_id is None:
                raise ValueError("inventory detail task requires a reservation identity")
        elif self.remote_id is not None:
            raise ValueError("only an inventory detail task may contain an identity")


@dataclass(frozen=True, slots=True)
class InventoryScopePage:
    scope: InventoryScope
    authenticated: bool | None
    requested_scope_visible: bool | None
    explicit_empty: bool | None
    pagination_exhausted: bool | None
    completeness: EvidenceCompleteness
    reservations: tuple[ObservedReservation, ...]
    visible_reservation_count: int
    detail_required_ids: tuple[str, ...]
    terminal_status: InventoryExecutionStatus | None = None


@dataclass(frozen=True, slots=True)
class InventoryDetailObservation:
    authenticated: bool | None
    reservation: ObservedReservation | None
    terminal_status: InventoryExecutionStatus | None = None


class InventorySemanticFailure(Enum):
    NO_ACTION = "no_action"
    PROPOSAL_REJECTED = "proposal_rejected"
    ACTION_FAILED = "action_failed"
    EXTRACTION_INVALID = "extraction_invalid"
    DESTINATION_CHANGED = "destination_changed"
    NON_ALLOWLISTED_DESTINATION = "non_allowlisted_destination"


@dataclass(frozen=True, slots=True)
class InventorySemanticPartial:
    scopes: tuple[ObservedInventoryScope, ...]
    reservations: tuple[ObservedReservation, ...]
    failure: InventorySemanticFailure


_SECURITY_TERMINALS = frozenset(
    {
        InventoryExecutionStatus.SESSION_UNAVAILABLE,
        InventoryExecutionStatus.SIGNED_OUT,
        InventoryExecutionStatus.MFA_REQUIRED,
        InventoryExecutionStatus.CAPTCHA,
        InventoryExecutionStatus.BOT_WALL,
        InventoryExecutionStatus.UNSAFE_ACTION,
    }
)


class InventoryComputerTurnKind(Enum):
    ACTION = "action"
    SUBMISSION = "submission"
    TERMINAL = "terminal"


@dataclass(frozen=True, slots=True)
class InventoryComputerObservation:
    authenticated: bool
    scopes: tuple[ObservedInventoryScope, ...]
    reservations: tuple[ObservedReservation, ...]
    evidence_item_count: int


@dataclass(frozen=True, slots=True)
class InventoryComputerTurn:
    kind: InventoryComputerTurnKind
    usage: ProviderUsage
    action: ComputerActionRequest | None = None
    observation: InventoryComputerObservation | None = None
    terminal_status: InventoryExecutionStatus | None = None

    def __post_init__(self) -> None:
        populated = sum(
            value is not None
            for value in (self.action, self.observation, self.terminal_status)
        )
        if populated != 1:
            raise ValueError("inventory computer turn requires exactly one typed outcome")


class InventoryStagehandRuntimePort(SessionRestoreTarget, Protocol):
    async def launch(self) -> None: ...
    async def apply_session(self) -> None: ...
    async def attach(self, api_key: str) -> None: ...
    async def navigate(self, url: str) -> None: ...
    async def destination(self) -> DestinationSnapshot: ...
    async def observe_inventory_action(
        self, task: InventoryTraversalTask
    ) -> tuple[SemanticAction | None, ProviderUsage]: ...
    async def inspect(self, action: SemanticAction) -> InspectedElement | None: ...
    async def replay(self, action: SemanticAction) -> None: ...
    async def extract_inventory_scope(self, scope: InventoryScope) -> tuple[
        InventoryScopePage, ProviderUsage
    ]: ...
    async def extract_inventory_detail(
        self, task: InventoryTraversalTask
    ) -> tuple[InventoryDetailObservation, ProviderUsage]: ...
    async def screenshot(self) -> bytes: ...
    async def hit_test(self, x: int, y: int) -> CoordinateHitTest | None: ...
    async def execute_action(self, action: ComputerActionRequest) -> None: ...
    async def verified_session_refresh(self) -> bytes | None: ...
    async def close(self) -> None: ...


class InventoryComputerUseModelPort(Protocol):
    def next_turn(
        self,
        *,
        screenshot: bytes,
        request: InventoryExecutionRequest,
        prior_tool_use_id: str | None,
    ) -> InventoryComputerTurn: ...


class InventoryActionGuard:
    """Separate safe page observation from task-specific interaction authority."""

    def evaluate(
        self,
        proposal: BrowserActionProposal,
        *,
        task: InventoryTraversalTask | None = None,
    ) -> GuardDecision:
        rejection = self._rejection(proposal, task=task)
        return GuardDecision(rejection is None, rejection)

    def validate_destination(
        self,
        before: DestinationSnapshot,
        after: DestinationSnapshot,
    ) -> GuardDecision:
        if after.popup_count > before.popup_count:
            return GuardDecision(False, GuardRejection.UNEXPECTED_POPUP)
        if _assess_destination(after.url).disposition is DestinationDisposition.DENY:
            return GuardDecision(False, GuardRejection.INVALID_DESTINATION)
        return GuardDecision(True)

    def _rejection(
        self,
        proposal: BrowserActionProposal,
        *,
        task: InventoryTraversalTask | None,
    ) -> GuardRejection | None:
        if proposal.current.popup_count:
            return GuardRejection.UNEXPECTED_POPUP
        current = _assess_destination(proposal.current.url)
        if current.disposition is DestinationDisposition.DENY:
            return GuardRejection.INVALID_DESTINATION
        if task is None and current.disposition is DestinationDisposition.OBSERVE_ONLY:
            return GuardRejection.INVALID_DESTINATION
        if proposal.destination is not None:
            destination = _assess_destination(proposal.destination)
            if destination.disposition is DestinationDisposition.DENY:
                return GuardRejection.INVALID_DESTINATION
        combined = f"{proposal.role} {proposal.label}"
        if _UNSAFE_INVENTORY_TEXT.search(combined):
            return GuardRejection.UNSAFE_LABEL
        if proposal.action is BrowserActionType.CLICK:
            return self._click_rejection(proposal, task=task)
        if proposal.action is BrowserActionType.SCROLL:
            if proposal.delta_x != 0 or not 0 < abs(proposal.delta_y) <= 1_200:
                return GuardRejection.UNSAFE_SCROLL
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
        # Inventory computer use never receives a typing capability.
        return (
            GuardRejection.UNSAFE_INPUT
            if proposal.action is BrowserActionType.TYPE
            else GuardRejection.UNSUPPORTED_ACTION
        )

    def _click_rejection(
        self,
        proposal: BrowserActionProposal,
        *,
        task: InventoryTraversalTask | None,
    ) -> GuardRejection | None:
        hit = proposal.hit_test
        if hit is not None:
            if not hit.in_viewport or proposal.x != hit.x or proposal.y != hit.y:
                return GuardRejection.INVALID_COORDINATE
            if not hit.visible or not hit.enabled:
                return GuardRejection.TARGET_NOT_ACTIONABLE
            if _UNSAFE_INVENTORY_TEXT.search(f"{hit.role} {hit.label}"):
                return GuardRejection.UNSAFE_LABEL
        elif proposal.x is not None or proposal.y is not None:
            return GuardRejection.INVALID_COORDINATE

        role = proposal.role.casefold()
        if role not in {"a", "button", "link", "tab"}:
            return GuardRejection.TARGET_NOT_ACTIONABLE
        label = " ".join(proposal.label.casefold().split())
        destination = proposal.destination
        if task is not None:
            return _task_click_rejection(task, role, label, destination)
        if _is_confirmation_destination(destination):
            return None
        if any(alias in label for aliases in _SCOPE_ALIASES.values() for alias in aliases):
            return None
        if _PAGINATION_TEXT.search(label) or _has_navigation_query(destination):
            return None
        return GuardRejection.UNSAFE_LABEL


def _task_click_rejection(
    task: InventoryTraversalTask,
    role: str,
    label: str,
    destination: str | None,
) -> GuardRejection | None:
    if task.kind is InventoryTaskKind.DETAIL:
        if not _DETAIL_TEXT.search(label):
            return GuardRejection.UNSAFE_LABEL
        if destination is not None and (
            _assess_destination(destination).disposition is DestinationDisposition.DENY
        ):
            return GuardRejection.UNSAFE_PATH
        return None
    if _is_confirmation_destination(destination):
        return GuardRejection.UNSAFE_PATH
    if task.kind is InventoryTaskKind.SCOPE:
        if role not in {"button", "link", "tab", "a"}:
            return GuardRejection.TARGET_NOT_ACTIONABLE
        return (
            None
            if any(alias in label for alias in _SCOPE_ALIASES[task.scope])
            or _destination_selects_scope(destination, task.scope)
            else GuardRejection.UNSAFE_LABEL
        )
    if _PAGINATION_TEXT.search(label) or _has_navigation_query(destination):
        return None
    return GuardRejection.UNSAFE_LABEL


def _is_confirmation_destination(url: str | None) -> bool:
    if url is None:
        return False
    assessment = _assess_destination(url)
    if assessment.category is not DestinationCategory.CONFIRMATION:
        return False
    parsed = urlsplit(url)
    query = parse_qs(parsed.query, keep_blank_values=True)
    return any(
        query.get(key) and all(value.strip() for value in query[key])
        for key in _CONFIRMATION_QUERY_KEYS
    )


def _assess_destination(url: str | None) -> DestinationAssessment:
    if url is None or len(url) > 2_000:
        return _destination_assessment(DestinationCategory.INVALID)
    try:
        parsed = urlsplit(url)
        pairs = parse_qsl(parsed.query, keep_blank_values=True)
    except (TypeError, ValueError):
        return _destination_assessment(DestinationCategory.INVALID)
    if not is_booking_destination(url):
        return _destination_assessment(
            DestinationCategory.EXTERNAL,
            parsed=parsed,
            pairs=pairs,
        )

    decoded_path = unquote(parsed.path)
    decoded_fragment = unquote(parsed.fragment)
    decoded_query = " ".join(
        f"{unquote(key)} {unquote(value)}" for key, value in pairs
    )
    path_fragment_text = _normalize_destination_text(f"{decoded_path} {decoded_fragment}")
    risk_text = _normalize_destination_text(f"{path_fragment_text} {decoded_query}")
    terminal_status = None
    if _CHALLENGE_DESTINATION_TEXT.search(risk_text):
        category = DestinationCategory.CHALLENGE
        terminal_status = (
            InventoryExecutionStatus.CAPTCHA
            if "captcha" in risk_text or "verify human" in risk_text
            else InventoryExecutionStatus.BOT_WALL
        )
    elif _AUTH_DESTINATION_TEXT.search(risk_text):
        category = DestinationCategory.AUTHENTICATION
        terminal_status = (
            InventoryExecutionStatus.MFA_REQUIRED
            if "two factor" in risk_text or "mfa" in risk_text
            else InventoryExecutionStatus.SIGNED_OUT
        )
    elif _MUTATION_DESTINATION_TEXT.search(risk_text) or _MUTATION_PATH_TEXT.search(
        path_fragment_text
    ):
        category = DestinationCategory.MUTATION
    elif _CONFIRMATION_DESTINATION_TEXT.search(risk_text):
        category = DestinationCategory.CONFIRMATION
    elif _INVENTORY_DESTINATION_TEXT.search(risk_text):
        category = DestinationCategory.INVENTORY
    else:
        category = DestinationCategory.UNKNOWN_BOOKING
    return _destination_assessment(
        category,
        parsed=parsed,
        pairs=pairs,
        terminal_status=terminal_status,
    )


def _destination_assessment(
    category: DestinationCategory,
    *,
    parsed: SplitResult | None = None,
    pairs: Sequence[tuple[str, str]] = (),
    terminal_status: InventoryExecutionStatus | None = None,
) -> DestinationAssessment:
    disposition = (
        DestinationDisposition.INTERACT
        if category in {DestinationCategory.INVENTORY, DestinationCategory.CONFIRMATION}
        else DestinationDisposition.OBSERVE_ONLY
        if category is DestinationCategory.UNKNOWN_BOOKING
        else DestinationDisposition.DENY
    )
    path = _sanitized_path_template(parsed.path if parsed is not None else "")
    keys = tuple(
        sorted(
            {
                key.casefold() if _SAFE_LOG_QUERY_KEY.fullmatch(key.casefold()) else "{key}"
                for key, _value in pairs
            }
        )[:16]
    )
    host_class = _host_class(parsed, category)
    return DestinationAssessment(
        disposition,
        category,
        host_class,
        path,
        keys,
        bool(parsed is not None and parsed.fragment),
        terminal_status,
    )


def _normalize_destination_text(value: str) -> str:
    camel_split = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", value)
    return " ".join(re.sub(r"[^a-z0-9]+", " ", camel_split.casefold()).split())


def _host_class(parsed: SplitResult | None, category: DestinationCategory) -> str:
    if parsed is None or not is_booking_destination(parsed.geturl()):
        return category.value
    host = (parsed.hostname or "").casefold().rstrip(".")
    return {
        "secure.booking.com": "secure_booking",
        "account.booking.com": "account_booking",
        "www.booking.com": "www_booking",
    }.get(host, "other_booking")


def _sanitized_path_template(path: str) -> str:
    components = []
    for raw in unquote(path).casefold().split("/"):
        if not raw:
            continue
        components.append(raw if raw in _SAFE_LOG_PATH_COMPONENTS else "{segment}")
        if len(components) == 8:
            break
    return "/" + "/".join(components) if components else "/"


def _log_destination_rejection(
    *, execution_id: str, phase: str, url: str | None, reason: GuardRejection
) -> None:
    assessment = _assess_destination(url)
    logger.warning(
        "Agentic inventory destination rejected execution_id=%s phase=%s category=%s "
        "host_class=%s path_template=%s query_keys=%s fragment_present=%s "
        "terminal_status=%s reason=%s",
        execution_id,
        phase,
        assessment.category.value,
        assessment.host_class,
        assessment.path_template,
        ",".join(assessment.query_keys) or "none",
        assessment.fragment_present,
        assessment.terminal_status.value if assessment.terminal_status is not None else "none",
        reason.value,
    )


def _has_navigation_query(url: str | None) -> bool:
    if url is None or _assess_destination(url).disposition is DestinationDisposition.DENY:
        return False
    query = parse_qs(urlsplit(url).query)
    return any(key in query for key in ("page", "cursor", "offset"))


def _destination_selects_scope(url: str | None, scope: InventoryScope) -> bool:
    if url is None or _assess_destination(url).disposition is DestinationDisposition.DENY:
        return False
    query = parse_qs(urlsplit(url).query)
    selected = {
        value.casefold()
        for key in ("scope", "status", "tab", "filter")
        for value in query.get(key, ())
    }
    return bool(selected.intersection(_SCOPE_ALIASES[scope]))


def _navigation_terminal(url: str) -> InventoryExecutionStatus | None:
    return _assess_destination(url).terminal_status


class LocalInventoryStagehandRuntime(LocalStagehandRuntime):
    """Inventory semantics over the shared isolated local Stagehand browser."""

    async def observe_inventory_action(
        self, task: InventoryTraversalTask
    ) -> tuple[SemanticAction | None, ProviderUsage]:
        stagehand = self._stagehand  # noqa: SLF001 - infrastructure specialization
        if stagehand is None:
            raise RuntimeError("Stagehand is not attached")
        instruction = _semantic_task_instruction(task)
        started = time.monotonic()
        result = await stagehand.observe(
            instruction,
            page=self._active_page(),  # noqa: SLF001 - infrastructure specialization
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

    async def extract_inventory_scope(
        self, scope: InventoryScope
    ) -> tuple[InventoryScopePage, ProviderUsage]:
        from pydantic import BaseModel, ConfigDict, Field

        class ExtractedReservation(BaseModel):
            model_config = ConfigDict(extra="forbid")
            remote_id: str = Field(min_length=1, max_length=128)
            identity_evidence: str
            lifecycle: str | None = None
            confirmation_id: str | None = Field(default=None, max_length=128)
            property_name: str | None = Field(default=None, max_length=500)
            property_reference: str | None = Field(default=None, max_length=500)
            check_in: str | None = None
            check_out: str | None = None
            room_type: str | None = Field(default=None, max_length=500)
            booked_total: str | None = Field(
                default=None, pattern=r"^[0-9]+(?:\.[0-9]{1,2})?$"
            )
            currency: str | None = Field(default=None, pattern=r"^[A-Z]{3}$")
            all_in: str
            refundability: str
            refundability_text: str | None = Field(default=None, max_length=1_000)
            refund_deadline: str | None = None
            adults: int | None = Field(default=None, ge=1, le=100)
            children: int | None = Field(default=None, ge=0, le=100)
            rooms: int | None = Field(default=None, ge=1, le=100)
            completeness: str
            needs_detail: bool

        class ExtractedScope(BaseModel):
            model_config = ConfigDict(extra="forbid")
            state: str
            authenticated: bool | None
            requested_scope_visible: bool | None
            explicit_empty: bool | None
            pagination_exhausted: bool | None
            completeness: str
            reservations: list[ExtractedReservation] = Field(max_length=500)

        stagehand = self._stagehand  # noqa: SLF001 - infrastructure specialization
        if stagehand is None:
            raise RuntimeError("Stagehand is not attached")
        started = time.monotonic()
        result = await stagehand.extract(
            _scope_extraction_instruction(scope),
            ExtractedScope,
            page=self._active_page(),  # noqa: SLF001 - infrastructure specialization
            timeout=45_000,
            screenshot=False,
            cache=False,
        )
        usage = _stagehand_usage(result.metadata, started)
        return _map_scope_page(scope, result.data.model_dump()), usage

    async def extract_inventory_detail(
        self, task: InventoryTraversalTask
    ) -> tuple[InventoryDetailObservation, ProviderUsage]:
        if task.kind is not InventoryTaskKind.DETAIL or task.remote_id is None:
            raise ValueError("detail extraction requires a detail task")
        from pydantic import BaseModel, ConfigDict, Field

        class ExtractedDetail(BaseModel):
            model_config = ConfigDict(extra="forbid")
            state: str
            authenticated: bool | None
            remote_id: str | None = Field(default=None, max_length=128)
            identity_evidence: str
            lifecycle: str | None = None
            confirmation_id: str | None = Field(default=None, max_length=128)
            property_name: str | None = Field(default=None, max_length=500)
            property_reference: str | None = Field(default=None, max_length=500)
            check_in: str | None = None
            check_out: str | None = None
            room_type: str | None = Field(default=None, max_length=500)
            booked_total: str | None = Field(
                default=None, pattern=r"^[0-9]+(?:\.[0-9]{1,2})?$"
            )
            currency: str | None = Field(default=None, pattern=r"^[A-Z]{3}$")
            all_in: str
            refundability: str
            refundability_text: str | None = Field(default=None, max_length=1_000)
            refund_deadline: str | None = None
            adults: int | None = Field(default=None, ge=1, le=100)
            children: int | None = Field(default=None, ge=0, le=100)
            rooms: int | None = Field(default=None, ge=1, le=100)
            completeness: str

        stagehand = self._stagehand  # noqa: SLF001 - infrastructure specialization
        if stagehand is None:
            raise RuntimeError("Stagehand is not attached")
        started = time.monotonic()
        result = await stagehand.extract(
            _detail_extraction_instruction(task),
            ExtractedDetail,
            page=self._active_page(),  # noqa: SLF001 - infrastructure specialization
            timeout=45_000,
            screenshot=False,
            cache=False,
        )
        usage = _stagehand_usage(result.metadata, started)
        raw = result.data.model_dump()
        status = _page_state_status(raw.get("state"))
        reservation = None
        if status is None and raw.get("remote_id") is not None:
            reservation = _map_reservation(task.scope, raw)
            if reservation.remote_id != task.remote_id:
                raise ValueError("detail identity conflicts with requested reservation")
        return (
            InventoryDetailObservation(
                authenticated=(
                    raw.get("authenticated")
                    if isinstance(raw.get("authenticated"), bool)
                    else None
                ),
                reservation=reservation,
                terminal_status=status,
            ),
            usage,
        )


def _semantic_task_instruction(task: InventoryTraversalTask) -> str:
    if task.kind is InventoryTaskKind.SCOPE:
        return (
            f"Find the visible read-only control that opens the {task.scope.value} reservations "
            "view. Propose only one click in the current tab; do not choose account, login, "
            "modify, cancel, booking, checkout, or payment controls."
        )
    if task.kind is InventoryTaskKind.PAGINATION:
        return (
            f"Find the visible read-only next-page or load-more control for the current "
            f"{task.scope.value} reservations list. Propose only one click in the current tab."
        )
    assert task.remote_id is not None
    return (
        "Find the read-only details link for the visible reservation whose exact stable identity "
        f"is {task.remote_id!r}. Propose only the click that opens its confirmation details in "
        "the current tab; never choose modify, cancel, booking, checkout, or payment controls."
    )


def _scope_extraction_instruction(scope: InventoryScope) -> str:
    return (
        f"Extract only visibly explicit evidence from the current {scope.value} reservations "
        "view. state must be inventory, signed_out, mfa_required, captcha, bot_wall, or "
        "unavailable. Omit cards without a stable remote identity. Use null or unknown evidence "
        "rather than inference. booked_total must be the explicit all-in stay total as a plain "
        "decimal and currency must be ISO-4217. Set needs_detail only when a visible read-only "
        "details link is required to obtain missing reservation facts. pagination_exhausted may "
        "be true only when the page visibly proves there is no next page."
    )


def _detail_extraction_instruction(task: InventoryTraversalTask) -> str:
    assert task.remote_id is not None
    return (
        "Extract only visibly explicit facts from this read-only Booking.com confirmation page "
        f"for stable identity {task.remote_id!r}. state must be inventory, signed_out, "
        "mfa_required, captcha, bot_wall, or unavailable. Do not infer missing facts, and return "
        "the visible identity so code can reject a mismatch."
    )


def _enum_value(enum_type: type[Enum], raw: object) -> Any:
    normalized = str(raw).strip().casefold()
    for member in enum_type:
        if str(member.value).casefold() == normalized:
            return member
    raise ValueError(f"unsupported {enum_type.__name__} value")


def _page_state_status(raw: object) -> InventoryExecutionStatus | None:
    normalized = str(raw).strip().casefold()
    if normalized == "inventory":
        return None
    mapping = {
        "signed_out": InventoryExecutionStatus.SIGNED_OUT,
        "mfa_required": InventoryExecutionStatus.MFA_REQUIRED,
        "captcha": InventoryExecutionStatus.CAPTCHA,
        "bot_wall": InventoryExecutionStatus.BOT_WALL,
        "unavailable": InventoryExecutionStatus.UNAVAILABLE,
    }
    try:
        return mapping[normalized]
    except KeyError as exc:
        raise ValueError("unsupported inventory page state") from exc


def _map_scope_page(scope: InventoryScope, raw: Mapping[str, Any]) -> InventoryScopePage:
    status = _page_state_status(raw.get("state"))
    raw_reservations = raw.get("reservations")
    if not isinstance(raw_reservations, Sequence) or isinstance(
        raw_reservations, (str, bytes)
    ):
        raise ValueError("inventory reservations must be a list")
    reservations: list[ObservedReservation] = []
    details: list[str] = []
    for item in raw_reservations:
        if not isinstance(item, Mapping):
            continue
        try:
            observation = _map_reservation(scope, item)
        except (InvalidOperation, TypeError, ValueError):
            continue
        reservations.append(observation)
        if item.get("needs_detail") is True:
            details.append(observation.remote_id)
    return InventoryScopePage(
        scope=scope,
        authenticated=(
            raw.get("authenticated")
            if isinstance(raw.get("authenticated"), bool)
            else None
        ),
        requested_scope_visible=(
            raw.get("requested_scope_visible")
            if isinstance(raw.get("requested_scope_visible"), bool)
            else None
        ),
        explicit_empty=(
            raw.get("explicit_empty")
            if isinstance(raw.get("explicit_empty"), bool)
            else None
        ),
        pagination_exhausted=(
            raw.get("pagination_exhausted")
            if isinstance(raw.get("pagination_exhausted"), bool)
            else None
        ),
        completeness=_enum_value(EvidenceCompleteness, raw.get("completeness")),
        reservations=tuple(reservations),
        visible_reservation_count=len(raw_reservations),
        detail_required_ids=tuple(dict.fromkeys(details))[:_MAX_DETAIL_TASKS],
        terminal_status=status,
    )


def _map_reservation(
    scope: InventoryScope,
    raw: Mapping[str, Any],
) -> ObservedReservation:
    check_in = date.fromisoformat(str(raw["check_in"])) if raw.get("check_in") else None
    check_out = date.fromisoformat(str(raw["check_out"])) if raw.get("check_out") else None
    total = None
    if raw.get("booked_total") is not None and raw.get("currency") is not None:
        total = Money.of(str(raw["booked_total"]), str(raw["currency"]))
    occupancy = None
    occupancy_values = (raw.get("adults"), raw.get("children"), raw.get("rooms"))
    if all(value is not None for value in occupancy_values):
        occupancy = Occupancy(
            adults=int(cast(int, occupancy_values[0])),
            children=int(cast(int, occupancy_values[1])),
            rooms=int(cast(int, occupancy_values[2])),
        )
    refundability = _enum_value(RefundabilityEvidence, raw.get("refundability"))
    return ObservedReservation(
        remote_id=str(raw["remote_id"]),
        identity_evidence=_enum_value(EvidenceCompleteness, raw.get("identity_evidence")),
        scope=scope,
        lifecycle=(
            _enum_value(ReservationLifecycle, raw.get("lifecycle"))
            if raw.get("lifecycle") is not None
            else None
        ),
        confirmation_id=(
            str(raw["confirmation_id"]) if raw.get("confirmation_id") is not None else None
        ),
        property_name=(
            str(raw["property_name"]) if raw.get("property_name") is not None else None
        ),
        property_reference=(
            str(raw["property_reference"])
            if raw.get("property_reference") is not None
            else None
        ),
        check_in=check_in,
        check_out=check_out,
        room_type=str(raw["room_type"]) if raw.get("room_type") is not None else None,
        booked_total=total,
        all_in=_enum_value(AllInEvidence, raw.get("all_in")),
        refundability=refundability,
        refundability_text=(
            str(raw["refundability_text"])
            if raw.get("refundability_text") is not None
            else None
        ),
        refund_deadline=(
            date.fromisoformat(str(raw["refund_deadline"]))
            if raw.get("refund_deadline") is not None
            else None
        ),
        occupancy=occupancy,
        completeness=_enum_value(EvidenceCompleteness, raw.get("completeness")),
    )


def _aggregate_scope(
    scope: InventoryScope,
    pages: Sequence[InventoryScopePage],
    *,
    detail_count: int,
) -> ObservedInventoryScope:
    visible_count = sum(page.visible_reservation_count for page in pages)
    requested_visible = (
        True
        if pages and all(page.requested_scope_visible is True for page in pages)
        else False
        if any(page.requested_scope_visible is False for page in pages)
        else None
    )
    pagination = pages[-1].pagination_exhausted if pages else None
    explicit_empty = (
        True
        if pages and visible_count == 0 and any(page.explicit_empty is True for page in pages)
        else False
        if visible_count > 0
        else None
    )
    completeness = (
        EvidenceCompleteness.COMPLETE
        if pages
        and requested_visible is True
        and pagination is True
        and all(page.completeness is EvidenceCompleteness.COMPLETE for page in pages)
        else EvidenceCompleteness.CONFLICTING
        if any(page.completeness is EvidenceCompleteness.CONFLICTING for page in pages)
        else EvidenceCompleteness.INCOMPLETE
    )
    return ObservedInventoryScope(
        scope=scope,
        requested_scope_visible=requested_visible,
        explicit_empty=explicit_empty,
        pagination_exhausted=pagination,
        pages_observed=len(pages),
        visible_reservation_count=visible_count,
        detail_count=detail_count,
        completeness=completeness,
    )


class AnthropicInventoryComputerUseModel:
    """Stateful Sonnet inventory observer with computer, submission, and terminal tools."""

    def __init__(self, api_key: str) -> None:
        from anthropic import Anthropic

        self._client = Anthropic(
            api_key=api_key,
            base_url=_ANTHROPIC_API_BASE,
            timeout=45.0,
            max_retries=0,
        )
        self._messages: list[dict[str, Any]] = []

    def next_turn(
        self,
        *,
        screenshot: bytes,
        request: InventoryExecutionRequest,
        prior_tool_use_id: str | None,
    ) -> InventoryComputerTurn:
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
                {"type": "text", "text": _computer_goal(request)},
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
                "You are a read-only Booking.com reservation inventory observer. Never type, "
                "authenticate, enter credentials, solve MFA/captcha, modify, cancel, reserve, "
                "book, pay, download, upload, or leave Booking.com. Use the typed submission "
                "tool for visible positive evidence only. Never infer that unseen reservations "
                "are absent or that an account is complete."
            ),
            tools=_computer_tools(),
            messages=self._messages,
        )
        usage = ProviderUsage(
            LLMUsage(
                input_tokens=int(response.usage.input_tokens),
                output_tokens=int(response.usage.output_tokens),
            ),
            max(0, round((time.monotonic() - started) * 1_000)),
        )
        assistant_content = [
            block.model_dump(exclude_none=True) if hasattr(block, "model_dump") else block
            for block in response.content
        ]
        self._messages.append({"role": "assistant", "content": assistant_content})
        tool_blocks = [
            block for block in response.content if getattr(block, "type", None) == "tool_use"
        ]
        if len(tool_blocks) != 1:
            raise ValueError("inventory computer use must return exactly one tool call")
        block = tool_blocks[0]
        raw = block.input
        if not isinstance(raw, Mapping):
            raise ValueError("inventory computer tool input must be an object")
        if block.name == "computer":
            try:
                action = _parse_computer_action(str(block.id), raw)
            except (TypeError, ValueError):
                return InventoryComputerTurn(
                    InventoryComputerTurnKind.TERMINAL,
                    usage,
                    terminal_status=InventoryExecutionStatus.UNSAFE_ACTION,
                )
            return InventoryComputerTurn(
                InventoryComputerTurnKind.ACTION,
                usage,
                action=action,
            )
        if block.name == "submit_inventory_observation":
            return InventoryComputerTurn(
                InventoryComputerTurnKind.SUBMISSION,
                usage,
                observation=_map_computer_observation(raw),
            )
        if block.name == "submit_terminal_outcome":
            return InventoryComputerTurn(
                InventoryComputerTurnKind.TERMINAL,
                usage,
                terminal_status=_terminal_status(raw.get("status")),
            )
        raise ValueError("unapproved inventory computer-use tool")


def _computer_goal(request: InventoryExecutionRequest) -> str:
    scopes = ", ".join(sorted(scope.value for scope in request.required_scopes))
    return (
        "Observe the currently open Booking.com reservation inventory for these code-owned "
        f"required views: {scopes}. Navigate only with read-only clicks, scrolling, safe keys, "
        "waits, or zoom. Typing is prohibited. Submit only visible positive reservation and "
        "scope evidence; never claim authoritative account completeness or absence."
    )


def _reservation_schema(*, needs_detail: bool) -> dict[str, Any]:
    properties: dict[str, Any] = {
        "remote_id": {"type": "string", "minLength": 1, "maxLength": 128},
        "identity_evidence": {"enum": [item.value for item in EvidenceCompleteness]},
        "scope": {"enum": [item.value for item in InventoryScope]},
        "lifecycle": {
            "type": ["string", "null"],
            "enum": [
                None,
                *[
                    item.value
                    for item in ReservationLifecycle
                    if item is not ReservationLifecycle.ABSENT
                ],
            ],
        },
        "confirmation_id": {"type": ["string", "null"], "maxLength": 128},
        "property_name": {"type": ["string", "null"], "maxLength": 500},
        "property_reference": {"type": ["string", "null"], "maxLength": 500},
        "check_in": {"type": ["string", "null"], "format": "date"},
        "check_out": {"type": ["string", "null"], "format": "date"},
        "room_type": {"type": ["string", "null"], "maxLength": 500},
        "booked_total": {
            "type": ["string", "null"],
            "pattern": r"^[0-9]+(?:\.[0-9]{1,2})?$",
        },
        "currency": {"type": ["string", "null"], "pattern": "^[A-Z]{3}$"},
        "all_in": {"enum": [item.value for item in AllInEvidence]},
        "refundability": {"enum": [item.value for item in RefundabilityEvidence]},
        "refundability_text": {"type": ["string", "null"], "maxLength": 1_000},
        "refund_deadline": {"type": ["string", "null"], "format": "date"},
        "adults": {"type": ["integer", "null"], "minimum": 1, "maximum": 100},
        "children": {"type": ["integer", "null"], "minimum": 0, "maximum": 100},
        "rooms": {"type": ["integer", "null"], "minimum": 1, "maximum": 100},
        "completeness": {"enum": [item.value for item in EvidenceCompleteness]},
    }
    if needs_detail:
        properties["needs_detail"] = {"type": "boolean"}
    return {
        "type": "object",
        "additionalProperties": False,
        "required": list(properties),
        "properties": properties,
    }


def _inventory_observation_schema() -> dict[str, Any]:
    scope = {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "scope",
            "requested_scope_visible",
            "explicit_empty",
            "pagination_exhausted",
            "pages_observed",
            "visible_reservation_count",
            "detail_count",
            "completeness",
        ],
        "properties": {
            "scope": {"enum": [item.value for item in InventoryScope]},
            "requested_scope_visible": {"type": ["boolean", "null"]},
            "explicit_empty": {"type": ["boolean", "null"]},
            "pagination_exhausted": {"type": ["boolean", "null"]},
            "pages_observed": {"type": "integer", "minimum": 1, "maximum": 20},
            "visible_reservation_count": {
                "type": "integer",
                "minimum": 0,
                "maximum": 500,
            },
            "detail_count": {"type": "integer", "minimum": 0, "maximum": 500},
            "completeness": {"enum": [item.value for item in EvidenceCompleteness]},
        },
    }
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["authenticated", "scopes", "reservations"],
        "properties": {
            "authenticated": {"type": "boolean"},
            "scopes": {"type": "array", "minItems": 1, "maxItems": 3, "items": scope},
            "reservations": {
                "type": "array",
                "maxItems": 500,
                "items": _reservation_schema(needs_detail=False),
            },
        },
    }


def _computer_tools() -> list[dict[str, Any]]:
    return [
        {
            "type": "computer_20251124",
            "name": "computer",
            "display_width_px": _VIEWPORT_WIDTH,
            "display_height_px": _VIEWPORT_HEIGHT,
            "enable_zoom": True,
            "strict": True,
        },
        {
            "name": "submit_inventory_observation",
            "description": "Submit visible positive reservation and traversal evidence.",
            "input_schema": _inventory_observation_schema(),
            "strict": True,
        },
        {
            "name": "submit_terminal_outcome",
            "description": "Stop with one closed non-success inventory outcome.",
            "input_schema": {
                "type": "object",
                "additionalProperties": False,
                "required": ["status"],
                "properties": {
                    "status": {
                        "enum": [
                            InventoryExecutionStatus.SIGNED_OUT.value,
                            InventoryExecutionStatus.MFA_REQUIRED.value,
                            InventoryExecutionStatus.CAPTCHA.value,
                            InventoryExecutionStatus.BOT_WALL.value,
                            InventoryExecutionStatus.UNAVAILABLE.value,
                            InventoryExecutionStatus.ACTION_LIMIT.value,
                            InventoryExecutionStatus.COST_LIMIT.value,
                            InventoryExecutionStatus.TIMEOUT.value,
                            InventoryExecutionStatus.PROVIDER_FAILURE.value,
                            InventoryExecutionStatus.VALIDATION_FAILURE.value,
                        ]
                    }
                },
            },
            "strict": True,
        },
    ]


def _map_computer_observation(raw: Mapping[str, Any]) -> InventoryComputerObservation:
    raw_scopes = raw.get("scopes")
    raw_reservations = raw.get("reservations")
    if not isinstance(raw_scopes, Sequence) or isinstance(raw_scopes, (str, bytes)):
        raise ValueError("computer inventory scopes must be a list")
    if not isinstance(raw_reservations, Sequence) or isinstance(
        raw_reservations, (str, bytes)
    ):
        raise ValueError("computer inventory reservations must be a list")
    scopes: list[ObservedInventoryScope] = []
    for item in raw_scopes:
        if not isinstance(item, Mapping):
            raise ValueError("computer inventory scope must be an object")
        scopes.append(
            ObservedInventoryScope(
                scope=_enum_value(InventoryScope, item.get("scope")),
                requested_scope_visible=(
                    item.get("requested_scope_visible")
                    if isinstance(item.get("requested_scope_visible"), bool)
                    else None
                ),
                explicit_empty=(
                    item.get("explicit_empty")
                    if isinstance(item.get("explicit_empty"), bool)
                    else None
                ),
                pagination_exhausted=(
                    item.get("pagination_exhausted")
                    if isinstance(item.get("pagination_exhausted"), bool)
                    else None
                ),
                pages_observed=int(item["pages_observed"]),
                visible_reservation_count=int(item["visible_reservation_count"]),
                detail_count=int(item["detail_count"]),
                completeness=_enum_value(EvidenceCompleteness, item.get("completeness")),
            )
        )
    reservations: list[ObservedReservation] = []
    for item in raw_reservations:
        if not isinstance(item, Mapping):
            continue
        try:
            scope = _enum_value(InventoryScope, item.get("scope"))
            reservations.append(_map_reservation(scope, item))
        except (InvalidOperation, TypeError, ValueError):
            continue
    authenticated = raw.get("authenticated")
    if not isinstance(authenticated, bool):
        raise ValueError("computer inventory authentication evidence must be boolean")
    return InventoryComputerObservation(
        authenticated=authenticated,
        scopes=tuple(scopes),
        reservations=tuple(reservations),
        evidence_item_count=len(scopes) * 8 + len(reservations) * 18,
    )


def _terminal_status(raw: object) -> InventoryExecutionStatus:
    status = InventoryExecutionStatus(str(raw))
    if status is InventoryExecutionStatus.OBSERVED:
        raise ValueError("terminal tool cannot submit an observation")
    return status


class StagehandInventoryBrowserExecutor:
    """Synchronous inventory port over one isolated semantic/visual browser episode."""

    def __init__(
        self,
        *,
        api_key: str,
        lease_broker: InMemorySessionLeaseBroker,
        budget: BrowserJobCostBudget,
        runner: AsyncLoopRunner,
        runtime_factory: Callable[[], InventoryStagehandRuntimePort] = (
            LocalInventoryStagehandRuntime
        ),
        computer_model_factory: Callable[[], InventoryComputerUseModelPort] | None = None,
        guard: InventoryActionGuard | None = None,
    ) -> None:
        if not api_key.strip():
            raise ValueError("BOOKSAVER_LLM_API_KEY is required for agentic inventory")
        if classify_executor_egress(_ANTHROPIC_API_BASE) is not ExecutorEgressKind.ANTHROPIC:
            raise RuntimeError("inventory model endpoint is outside the executor allowlist")
        self._api_key = api_key
        self._leases = lease_broker
        self._budget = budget
        self._runner = runner
        self._runtime_factory = runtime_factory
        self._computer_model_factory = computer_model_factory or (
            lambda: AnthropicInventoryComputerUseModel(api_key)
        )
        self._guard = guard or InventoryActionGuard()

    def execute(self, request: InventoryExecutionRequest) -> InventoryExecutionResult:
        remaining = (request.limits.deadline - datetime.now(UTC)).total_seconds()
        timeout = max(0.001, min(float(request.limits.timeout_seconds), remaining))
        started = time.monotonic()
        meter = ExecutionMeter(request.limits)
        try:
            return self._runner.run(
                self._execute(request, started, meter),
                timeout=timeout,
            )
        except TimeoutError:
            return self._terminal(InventoryExecutionStatus.TIMEOUT, meter, started)
        except Exception as exc:
            logger.warning(
                "Agentic inventory execution failed execution_id=%s failure_type=%s",
                request.execution_id,
                type(exc).__name__,
            )
            return self._terminal(InventoryExecutionStatus.PROVIDER_FAILURE, meter, started)

    async def _execute(
        self,
        request: InventoryExecutionRequest,
        started: float,
        meter: ExecutionMeter,
    ) -> InventoryExecutionResult:
        runtime = self._runtime_factory()
        fallback_used = False
        try:
            await runtime.launch()
            self._leases.restore_into(request.session_lease, runtime)
            await runtime.apply_session()
            await runtime.attach(self._api_key)
            before = await runtime.destination()
            meter.record_action()
            await runtime.navigate(INVENTORY_ENTRY_URL)
            after_entry = await runtime.destination()
            navigation_terminal = _navigation_terminal(after_entry.url)
            if navigation_terminal is not None:
                _log_destination_rejection(
                    execution_id=request.execution_id,
                    phase="entry_redirect",
                    url=after_entry.url,
                    reason=GuardRejection.INVALID_DESTINATION,
                )
                return self._terminal(navigation_terminal, meter, started)
            entry_decision = self._guard.validate_destination(before, after_entry)
            if not entry_decision.allowed:
                _log_destination_rejection(
                    execution_id=request.execution_id,
                    phase="entry_redirect",
                    url=after_entry.url,
                    reason=entry_decision.rejection or GuardRejection.INVALID_DESTINATION,
                )
                return self._unsafe_destination(meter, started)

            semantic = await self._semantic_episode(runtime, request, meter, started)
            if isinstance(semantic, InventoryExecutionResult):
                if semantic.status is not InventoryExecutionStatus.OBSERVED:
                    return semantic
                return await self._with_verified_refresh(runtime, request, semantic, started)
            semantic_failure = (
                semantic.failure
                if isinstance(semantic, InventorySemanticPartial)
                else semantic
            )
            if semantic_failure in {
                InventorySemanticFailure.DESTINATION_CHANGED,
                InventorySemanticFailure.NON_ALLOWLISTED_DESTINATION,
            }:
                violations = {ExecutorSafetyViolation.PROHIBITED_ACTION_EXECUTED}
                if semantic_failure is InventorySemanticFailure.NON_ALLOWLISTED_DESTINATION:
                    violations.add(ExecutorSafetyViolation.NON_ALLOWLISTED_DESTINATION)
                return self._terminal(
                    InventoryExecutionStatus.UNSAFE_ACTION,
                    meter,
                    started,
                    safety_violations=frozenset(violations),
                )

            fallback_used = True
            visual = await self._computer_episode(runtime, request, meter, started)
            if visual.status is InventoryExecutionStatus.OBSERVED:
                if isinstance(semantic, InventorySemanticPartial):
                    visual = self._merge_partial_visual(
                        semantic,
                        visual,
                        meter,
                        started,
                    )
                return await self._with_verified_refresh(runtime, request, visual, started)
            if (
                isinstance(semantic, InventorySemanticPartial)
                and visual.status not in _SECURITY_TERMINALS
            ):
                partial = self._observed(
                    authenticated=True,
                    scopes=semantic.scopes,
                    reservations=semantic.reservations,
                    source=ObservationSource.STAGEHAND_INVENTORY_EXTRACT,
                    meter=meter,
                    started=started,
                    fallback_used=True,
                )
                return await self._with_verified_refresh(runtime, request, partial, started)
            return visual
        except RuntimeError as exc:
            detail = str(exc)
            status = (
                InventoryExecutionStatus.ACTION_LIMIT
                if "action limit exhausted" in detail
                else InventoryExecutionStatus.COST_LIMIT
                if "cost limit exhausted" in detail
                else InventoryExecutionStatus.PROVIDER_FAILURE
            )
            return self._terminal(status, meter, started, fallback_used=fallback_used)
        finally:
            try:
                await runtime.close()
            except Exception as exc:
                logger.warning(
                    "Agentic inventory cleanup failed execution_id=%s failure_type=%s",
                    request.execution_id,
                    type(exc).__name__,
                )

    async def _semantic_episode(
        self,
        runtime: InventoryStagehandRuntimePort,
        request: InventoryExecutionRequest,
        meter: ExecutionMeter,
        started: float,
    ) -> InventoryExecutionResult | InventorySemanticFailure | InventorySemanticPartial:
        pages_by_scope: dict[InventoryScope, list[InventoryScopePage]] = {}
        reservations: dict[str, ObservedReservation] = {}
        reservation_evidence: list[ObservedReservation] = []
        detail_tasks: list[tuple[InventoryScope, int, str]] = []
        detail_counts: dict[InventoryScope, int] = {scope: 0 for scope in request.required_scopes}
        authenticated = True

        ordered_scopes = tuple(
            scope
            for scope in (
                InventoryScope.UPCOMING,
                InventoryScope.PAST,
                InventoryScope.CANCELLED,
            )
            if scope in request.required_scopes
        )
        for scope_index, scope in enumerate(ordered_scopes):
            if scope_index:
                action_result = await self._perform_semantic_action(
                    runtime,
                    request,
                    meter,
                    InventoryTraversalTask(InventoryTaskKind.SCOPE, scope),
                )
                if action_result is not None:
                    return self._partial_or_failure(
                        pages_by_scope,
                        reservation_evidence,
                        detail_counts,
                        authenticated,
                        action_result,
                    )
            pages: list[InventoryScopePage] = []
            pages_by_scope[scope] = pages
            for page_number in range(1, _MAX_SCOPE_PAGES + 1):
                page = await self._extract_scope(runtime, scope, meter)
                if isinstance(page, InventorySemanticFailure):
                    return self._partial_or_failure(
                        pages_by_scope,
                        reservation_evidence,
                        detail_counts,
                        authenticated,
                        page,
                    )
                if page.terminal_status is not None:
                    return self._terminal(page.terminal_status, meter, started)
                if page.authenticated is False:
                    return self._terminal(InventoryExecutionStatus.SIGNED_OUT, meter, started)
                if page.authenticated is not True:
                    return self._partial_or_failure(
                        pages_by_scope,
                        reservation_evidence,
                        detail_counts,
                        authenticated,
                        InventorySemanticFailure.EXTRACTION_INVALID,
                    )
                if page.requested_scope_visible is not True:
                    return self._partial_or_failure(
                        pages_by_scope,
                        reservation_evidence,
                        detail_counts,
                        authenticated,
                        InventorySemanticFailure.EXTRACTION_INVALID,
                    )
                pages.append(page)
                for observation in page.reservations:
                    previous = reservations.get(observation.remote_id)
                    if previous is not None and previous != observation:
                        return self._partial_or_failure(
                            pages_by_scope,
                            reservation_evidence,
                            detail_counts,
                            authenticated,
                            InventorySemanticFailure.EXTRACTION_INVALID,
                        )
                    reservations[observation.remote_id] = observation
                    if previous is None:
                        reservation_evidence.append(observation)
                detail_tasks.extend(
                    (scope, page_number, remote_id)
                    for remote_id in page.detail_required_ids
                )
                if page.pagination_exhausted is True:
                    break
                action_result = await self._perform_semantic_action(
                    runtime,
                    request,
                    meter,
                    InventoryTraversalTask(InventoryTaskKind.PAGINATION, scope),
                )
                if action_result is not None:
                    return self._partial_or_failure(
                        pages_by_scope,
                        reservation_evidence,
                        detail_counts,
                        authenticated,
                        action_result,
                    )

        detail_failure: InventorySemanticFailure | None = None
        for scope, page_number, remote_id in detail_tasks[:_MAX_DETAIL_TASKS]:
            # Detail work is opportunistic. Preserve the positive list observation when the
            # remaining action allowance cannot safely replay its code-owned path.
            required_actions = 2 + int(scope is not InventoryScope.UPCOMING) + page_number - 1
            if meter.snapshot().total_actions + required_actions > request.limits.max_actions:
                break
            meter.record_action()
            before = await runtime.destination()
            await runtime.navigate(INVENTORY_ENTRY_URL)
            if not self._guard.validate_destination(
                before,
                await runtime.destination(),
            ).allowed:
                return self._partial_or_failure(
                    pages_by_scope,
                    reservation_evidence,
                    detail_counts,
                    authenticated,
                    InventorySemanticFailure.NON_ALLOWLISTED_DESTINATION,
                )
            if scope is not InventoryScope.UPCOMING:
                failure = await self._perform_semantic_action(
                    runtime,
                    request,
                    meter,
                    InventoryTraversalTask(InventoryTaskKind.SCOPE, scope),
                )
                if failure is not None:
                    detail_failure = failure
                    break
            for _ in range(page_number - 1):
                failure = await self._perform_semantic_action(
                    runtime,
                    request,
                    meter,
                    InventoryTraversalTask(InventoryTaskKind.PAGINATION, scope),
                )
                if failure is not None:
                    detail_failure = failure
                    break
            else:
                failure = await self._perform_semantic_action(
                    runtime,
                    request,
                    meter,
                    InventoryTraversalTask(InventoryTaskKind.DETAIL, scope, remote_id),
                )
                if failure is None:
                    detail = await self._extract_detail(
                        runtime,
                        InventoryTraversalTask(InventoryTaskKind.DETAIL, scope, remote_id),
                        meter,
                    )
                    if isinstance(detail, InventoryDetailObservation):
                        if detail.terminal_status is not None:
                            return self._terminal(
                                detail.terminal_status,
                                meter,
                                started,
                            )
                        if detail.authenticated is not True or detail.reservation is None:
                            continue
                        reservation_evidence.append(detail.reservation)
                        detail_counts[scope] += 1
                    else:
                        detail_failure = detail
                else:
                    detail_failure = failure
            if detail_failure is not None:
                break

        if detail_failure is not None:
            return self._partial_or_failure(
                pages_by_scope,
                reservation_evidence,
                detail_counts,
                authenticated,
                detail_failure,
            )

        scopes = tuple(
            _aggregate_scope(
                scope,
                pages_by_scope.get(scope, ()),
                detail_count=detail_counts[scope],
            )
            for scope in ordered_scopes
            if pages_by_scope.get(scope)
        )
        if not authenticated or not scopes:
            return InventorySemanticFailure.EXTRACTION_INVALID
        return self._observed(
            authenticated=True,
            scopes=scopes,
            reservations=tuple(reservation_evidence),
            source=ObservationSource.STAGEHAND_INVENTORY_EXTRACT,
            meter=meter,
            started=started,
            fallback_used=False,
        )

    @staticmethod
    def _partial_or_failure(
        pages_by_scope: Mapping[InventoryScope, Sequence[InventoryScopePage]],
        reservations: Sequence[ObservedReservation],
        detail_counts: Mapping[InventoryScope, int],
        authenticated: bool,
        failure: InventorySemanticFailure,
    ) -> InventorySemanticFailure | InventorySemanticPartial:
        scopes = tuple(
            _aggregate_scope(
                scope,
                pages,
                detail_count=detail_counts.get(scope, 0),
            )
            for scope, pages in pages_by_scope.items()
            if pages
        )
        if authenticated and scopes:
            return InventorySemanticPartial(scopes, tuple(reservations), failure)
        return failure

    async def _perform_semantic_action(
        self,
        runtime: InventoryStagehandRuntimePort,
        request: InventoryExecutionRequest,
        meter: ExecutionMeter,
        task: InventoryTraversalTask,
    ) -> InventorySemanticFailure | None:
        admitted = self._admit(ModelRole.RECOVERY, "stagehand-inventory-observe-v1")
        if admitted is None:
            return InventorySemanticFailure.ACTION_FAILED
        try:
            action, usage = await runtime.observe_inventory_action(task)
        except asyncio.CancelledError:
            self._reconcile_failure(admitted, meter)
            raise
        except Exception:
            self._reconcile_failure(admitted, meter)
            return InventorySemanticFailure.ACTION_FAILED
        self._reconcile_success(admitted, usage, meter)
        if action is None:
            return InventorySemanticFailure.NO_ACTION
        if action.method not in {"click", "locator.click"}:
            return InventorySemanticFailure.PROPOSAL_REJECTED
        inspected = await runtime.inspect(action)
        if inspected is None or not inspected.visible or not inspected.enabled:
            return InventorySemanticFailure.PROPOSAL_REJECTED
        before = await runtime.destination()
        proposal = BrowserActionProposal(
            action=BrowserActionType.CLICK,
            current=before,
            # Provider prose is untrusted intent, not target evidence. Authorization is based
            # only on the code-inspected DOM target that will actually receive the replay.
            label=inspected.label,
            role=inspected.role,
            destination=inspected.href,
        )
        guard_decision = self._guard.evaluate(proposal, task=task)
        if not guard_decision.allowed:
            _log_destination_rejection(
                execution_id=request.execution_id,
                phase="semantic_pre_action",
                url=(
                    inspected.href
                    if inspected.href is not None
                    and _assess_destination(inspected.href).disposition
                    is DestinationDisposition.DENY
                    else before.url
                ),
                reason=guard_decision.rejection or GuardRejection.UNSUPPORTED_ACTION,
            )
            return InventorySemanticFailure.PROPOSAL_REJECTED
        meter.record_action()
        try:
            await runtime.replay(action)
        except Exception:
            try:
                after_failure = await runtime.destination()
                post_failure = self._guard.validate_destination(before, after_failure)
            except Exception:
                return InventorySemanticFailure.ACTION_FAILED
            if not post_failure.allowed:
                _log_destination_rejection(
                    execution_id=request.execution_id,
                    phase="semantic_post_action_error",
                    url=after_failure.url,
                    reason=post_failure.rejection or GuardRejection.INVALID_DESTINATION,
                )
                return (
                    InventorySemanticFailure.NON_ALLOWLISTED_DESTINATION
                    if post_failure.rejection is GuardRejection.INVALID_DESTINATION
                    else InventorySemanticFailure.DESTINATION_CHANGED
                )
            return InventorySemanticFailure.ACTION_FAILED
        after = await runtime.destination()
        decision = self._guard.validate_destination(before, after)
        if not decision.allowed:
            _log_destination_rejection(
                execution_id=request.execution_id,
                phase="semantic_post_action",
                url=after.url,
                reason=decision.rejection or GuardRejection.INVALID_DESTINATION,
            )
            return (
                InventorySemanticFailure.NON_ALLOWLISTED_DESTINATION
                if decision.rejection is GuardRejection.INVALID_DESTINATION
                else InventorySemanticFailure.DESTINATION_CHANGED
            )
        return None

    async def _extract_scope(
        self,
        runtime: InventoryStagehandRuntimePort,
        scope: InventoryScope,
        meter: ExecutionMeter,
    ) -> InventoryScopePage | InventorySemanticFailure:
        admitted = self._admit(ModelRole.EXTRACTION, "stagehand-inventory-extract-v1")
        if admitted is None:
            return InventorySemanticFailure.EXTRACTION_INVALID
        try:
            page, usage = await runtime.extract_inventory_scope(scope)
        except asyncio.CancelledError:
            self._reconcile_failure(admitted, meter)
            raise
        except Exception:
            self._reconcile_failure(admitted, meter)
            return InventorySemanticFailure.EXTRACTION_INVALID
        self._reconcile_success(admitted, usage, meter)
        return page

    async def _extract_detail(
        self,
        runtime: InventoryStagehandRuntimePort,
        task: InventoryTraversalTask,
        meter: ExecutionMeter,
    ) -> InventoryDetailObservation | InventorySemanticFailure:
        admitted = self._admit(ModelRole.EXTRACTION, "stagehand-inventory-detail-v1")
        if admitted is None:
            return InventorySemanticFailure.EXTRACTION_INVALID
        try:
            observation, usage = await runtime.extract_inventory_detail(task)
        except asyncio.CancelledError:
            self._reconcile_failure(admitted, meter)
            raise
        except Exception:
            self._reconcile_failure(admitted, meter)
            return InventorySemanticFailure.EXTRACTION_INVALID
        self._reconcile_success(admitted, usage, meter)
        return observation

    async def _computer_episode(
        self,
        runtime: InventoryStagehandRuntimePort,
        request: InventoryExecutionRequest,
        meter: ExecutionMeter,
        started: float,
    ) -> InventoryExecutionResult:
        model = self._computer_model_factory()
        prior_tool_use_id: str | None = None
        while True:
            admitted = self._admit(ModelRole.RECOVERY, "anthropic-computer-use-inventory-v1")
            if admitted is None:
                return self._terminal(
                    InventoryExecutionStatus.COST_LIMIT,
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
                    InventoryExecutionStatus.PROVIDER_FAILURE,
                    meter,
                    started,
                    fallback_used=True,
                )
            self._reconcile_success(admitted, turn.usage, meter)
            if turn.kind is InventoryComputerTurnKind.SUBMISSION:
                assert turn.observation is not None
                if not turn.observation.authenticated:
                    return self._terminal(
                        InventoryExecutionStatus.SIGNED_OUT,
                        meter,
                        started,
                        fallback_used=True,
                    )
                return self._observed(
                    authenticated=True,
                    scopes=turn.observation.scopes,
                    reservations=turn.observation.reservations,
                    source=ObservationSource.COMPUTER_USE_INVENTORY_SUBMISSION,
                    meter=meter,
                    started=started,
                    fallback_used=True,
                    evidence_item_count=turn.observation.evidence_item_count,
                )
            if turn.kind is InventoryComputerTurnKind.TERMINAL:
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
                    InventoryExecutionStatus.ACTION_LIMIT,
                    meter,
                    started,
                    fallback_used=True,
                )
            before = await runtime.destination()
            hit = None
            label = ""
            role = ""
            destination = None
            if turn.action.action is BrowserActionType.CLICK:
                assert turn.action.x is not None and turn.action.y is not None
                hit = await runtime.hit_test(turn.action.x, turn.action.y)
                if hit is not None:
                    label, role, destination = hit.label, hit.role, hit.href
            proposal = BrowserActionProposal(
                action=turn.action.action,
                current=before,
                label=label,
                role=role,
                destination=destination,
                value=turn.action.value,
                x=turn.action.x,
                y=turn.action.y,
                delta_y=turn.action.delta_y,
                wait_ms=turn.action.wait_ms,
                zoom_region=turn.action.zoom_region,
                viewport_width=_VIEWPORT_WIDTH,
                viewport_height=_VIEWPORT_HEIGHT,
                hit_test=hit,
            )
            decision = self._guard.evaluate(proposal)
            if not decision.allowed:
                logger.info(
                    "Agentic inventory action rejected execution_id=%s code=%s",
                    request.execution_id,
                    (decision.rejection or GuardRejection.UNSUPPORTED_ACTION).value,
                )
                _log_destination_rejection(
                    execution_id=request.execution_id,
                    phase="computer_pre_action",
                    url=(
                        destination
                        if destination is not None
                        and _assess_destination(destination).disposition
                        is DestinationDisposition.DENY
                        else before.url
                    ),
                    reason=decision.rejection or GuardRejection.UNSUPPORTED_ACTION,
                )
                return self._terminal(
                    InventoryExecutionStatus.UNSAFE_ACTION,
                    meter,
                    started,
                    fallback_used=True,
                )
            executable_action = turn.action
            if turn.action.action is BrowserActionType.KEY:
                assert turn.action.value is not None
                executable_action = replace(
                    turn.action,
                    value=_CANONICAL_SAFE_KEYS[turn.action.value.upper()],
                )
            meter.record_action(computer_use=True)
            try:
                await runtime.execute_action(executable_action)
            except Exception:
                try:
                    after_failure = await runtime.destination()
                    post_failure = self._guard.validate_destination(before, after_failure)
                except Exception:
                    return self._terminal(
                        InventoryExecutionStatus.PROVIDER_FAILURE,
                        meter,
                        started,
                        fallback_used=True,
                    )
                if not post_failure.allowed:
                    _log_destination_rejection(
                        execution_id=request.execution_id,
                        phase="computer_post_action_error",
                        url=after_failure.url,
                        reason=post_failure.rejection or GuardRejection.INVALID_DESTINATION,
                    )
                    violations = {ExecutorSafetyViolation.PROHIBITED_ACTION_EXECUTED}
                    if post_failure.rejection is GuardRejection.INVALID_DESTINATION:
                        violations.add(ExecutorSafetyViolation.NON_ALLOWLISTED_DESTINATION)
                    return self._terminal(
                        InventoryExecutionStatus.UNSAFE_ACTION,
                        meter,
                        started,
                        fallback_used=True,
                        safety_violations=frozenset(violations),
                    )
                return self._terminal(
                    InventoryExecutionStatus.PROVIDER_FAILURE,
                    meter,
                    started,
                    fallback_used=True,
                )
            after = await runtime.destination()
            post = self._guard.validate_destination(before, after)
            if not post.allowed:
                _log_destination_rejection(
                    execution_id=request.execution_id,
                    phase="computer_post_action",
                    url=after.url,
                    reason=post.rejection or GuardRejection.INVALID_DESTINATION,
                )
                violations = {ExecutorSafetyViolation.PROHIBITED_ACTION_EXECUTED}
                if post.rejection is GuardRejection.INVALID_DESTINATION:
                    violations.add(ExecutorSafetyViolation.NON_ALLOWLISTED_DESTINATION)
                return self._terminal(
                    InventoryExecutionStatus.UNSAFE_ACTION,
                    meter,
                    started,
                    fallback_used=True,
                    safety_violations=frozenset(violations),
                )
            prior_tool_use_id = turn.action.tool_use_id

    async def _with_verified_refresh(
        self,
        runtime: InventoryStagehandRuntimePort,
        request: InventoryExecutionRequest,
        result: InventoryExecutionResult,
        started: float,
    ) -> InventoryExecutionResult:
        try:
            refreshed = await runtime.verified_session_refresh()
            if refreshed is None:
                return self._terminal(
                    InventoryExecutionStatus.SESSION_UNAVAILABLE,
                    meter=None,
                    started=started,
                    usage=result.usage,
                    fallback_used=result.fallback_used,
                )
            self._leases.store_verified_refresh(request.session_lease, refreshed)
            return replace(result, refreshed_session_eligible=True)
        except Exception as exc:
            logger.warning(
                "Agentic inventory session proof failed execution_id=%s failure_type=%s",
                request.execution_id,
                type(exc).__name__,
            )
            return self._terminal(
                InventoryExecutionStatus.SESSION_UNAVAILABLE,
                meter=None,
                started=started,
                usage=result.usage,
                fallback_used=result.fallback_used,
            )

    @staticmethod
    def _merge_partial_visual(
        partial: InventorySemanticPartial,
        visual: InventoryExecutionResult,
        meter: ExecutionMeter,
        started: float,
    ) -> InventoryExecutionResult:
        scope_by_kind = {scope.scope: scope for scope in partial.scopes}
        scope_by_kind.update({scope.scope: scope for scope in visual.scopes})
        evidence_count = (
            (visual.provenance.evidence_item_count if visual.provenance is not None else 0)
            + len(partial.scopes) * 8
            + len(partial.reservations) * 18
        )
        return StagehandInventoryBrowserExecutor._observed(
            authenticated=True,
            scopes=tuple(scope_by_kind.values()),
            reservations=partial.reservations + visual.reservations,
            source=ObservationSource.COMPUTER_USE_INVENTORY_SUBMISSION,
            meter=meter,
            started=started,
            fallback_used=True,
            evidence_item_count=evidence_count,
        )

    def _admit(self, role: ModelRole, prompt_version: str) -> AdmittedModelAttempt | None:
        profile = AdaptiveModelPortfolio().primary(role, prompt_version)
        return self._budget.admit(
            ModelAttemptPlan(1, profile, EscalationTrigger.INITIAL_AMBIGUOUS),
            _MODEL_ENVELOPE,
        ).attempt

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
        *,
        authenticated: bool,
        scopes: tuple[ObservedInventoryScope, ...],
        reservations: tuple[ObservedReservation, ...],
        source: ObservationSource,
        meter: ExecutionMeter,
        started: float,
        fallback_used: bool,
        evidence_item_count: int | None = None,
    ) -> InventoryExecutionResult:
        usage = meter.snapshot()
        return InventoryExecutionResult(
            InventoryExecutionStatus.OBSERVED,
            authenticated=authenticated,
            scopes=scopes,
            reservations=reservations,
            provenance=RedactedProvenance(
                source=source,
                action_count=usage.total_actions,
                evidence_item_count=(
                    evidence_item_count
                    if evidence_item_count is not None
                    else len(scopes) * 8 + len(reservations) * 18
                ),
                schema_version="inventory-observation-v1",
            ),
            usage=usage,
            latency_ms=max(0, round((time.monotonic() - started) * 1_000)),
            fallback_used=fallback_used,
        )

    @staticmethod
    def _terminal(
        status: InventoryExecutionStatus,
        meter: ExecutionMeter | None,
        started: float,
        *,
        usage: ExecutionUsage | None = None,
        fallback_used: bool = False,
        safety_violations: frozenset[ExecutorSafetyViolation] = frozenset(),
    ) -> InventoryExecutionResult:
        resolved_usage = meter.snapshot() if meter is not None else usage
        if resolved_usage is None:
            raise ValueError("terminal inventory result requires execution usage")
        return InventoryExecutionResult(
            status,
            usage=resolved_usage,
            latency_ms=max(0, round((time.monotonic() - started) * 1_000)),
            fallback_used=fallback_used,
            safety_violations=safety_violations,
        )

    @staticmethod
    def _unsafe_destination(
        meter: ExecutionMeter,
        started: float,
    ) -> InventoryExecutionResult:
        return StagehandInventoryBrowserExecutor._terminal(
            InventoryExecutionStatus.UNSAFE_ACTION,
            meter,
            started,
            safety_violations=frozenset(
                {ExecutorSafetyViolation.NON_ALLOWLISTED_DESTINATION}
            ),
        )


class LocalAgenticInventoryExecutor:
    """One-shot inventory executor that owns and closes its async runner."""

    def __init__(
        self,
        *,
        api_key: str,
        lease_broker: InMemorySessionLeaseBroker,
        budget: BrowserJobCostBudget,
    ) -> None:
        self._api_key = api_key
        self._leases = lease_broker
        self._budget = budget

    def execute(self, request: InventoryExecutionRequest) -> InventoryExecutionResult:
        with AsyncLoopRunner() as runner:
            return StagehandInventoryBrowserExecutor(
                api_key=self._api_key,
                lease_broker=self._leases,
                budget=self._budget,
                runner=runner,
            ).execute(request)
