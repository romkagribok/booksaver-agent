from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, date, datetime
from enum import Enum

from .value_objects import Money, Occupancy


class InventoryCompleteness(Enum):
    COMPLETE = "complete"
    INCOMPLETE = "incomplete"
    FAILED = "failed"


class ReservationLifecycle(Enum):
    UPCOMING = "upcoming"
    CURRENT = "current"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    UNKNOWN = "unknown"
    ABSENT = "absent"


class EligibilityStatus(Enum):
    ELIGIBLE = "eligible"
    INELIGIBLE = "ineligible"


class EligibilityReason(Enum):
    PAST_OR_COMPLETED = "past_or_completed"
    CANCELLED = "cancelled"
    NOT_UPCOMING = "not_upcoming"
    NON_REFUNDABLE = "non_refundable"
    REFUNDABILITY_UNKNOWN = "refundability_unknown"
    MISSING_CONFIRMATION = "missing_confirmation"
    MISSING_PROPERTY = "missing_property"
    MISSING_STAY_DATES = "missing_stay_dates"
    MISSING_ROOM_TYPE = "missing_room_type"
    MISSING_OCCUPANCY = "missing_occupancy"
    MISSING_BOOKED_TOTAL = "missing_booked_total"
    NOT_OBSERVED = "not_observed"


class SynchronizationTrigger(Enum):
    CONNECT = "connect"
    SESSION_INTAKE = "session_intake"
    SCHEDULED = "scheduled"
    CHECK_NOW = "check_now"
    BOOKINGS = "bookings"


class SynchronizationFailureCode(Enum):
    AUTH_REQUIRED = "auth_required"
    USER_KEY_INVALID = "user_key_invalid"
    BOT_WALL = "bot_wall"
    NAVIGATION_FAILED = "navigation_failed"
    UNSUPPORTED_LAYOUT = "unsupported_layout"
    PAGINATION_INCOMPLETE = "pagination_incomplete"
    IDENTITY_AMBIGUOUS = "identity_ambiguous"
    EXTRACTION_AMBIGUOUS = "extraction_ambiguous"
    PERSISTENCE_CONFLICT = "persistence_conflict"
    UNKNOWN = "unknown"


class InventoryRecoveryOutcome(Enum):
    """Redacted outcome of optional LLM assistance during inventory discovery."""

    NOT_NEEDED = "not_needed"
    RECOVERED = "recovered"
    PARTIAL = "partial"
    UNAVAILABLE = "unavailable"
    GAVE_UP = "gave_up"
    BLOCKED = "blocked"
    PROVIDER_ERROR = "provider_error"
    BUDGET_EXHAUSTED = "budget_exhausted"


_AUDIT_CODE_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_MAX_AUDIT_TRACE_EVENTS = 256
_MAX_AUDIT_LLM_CALLS = 10_000
_MAX_AUDIT_ACTIONS = 100_000
_MAX_AUDIT_TOKENS = 100_000_000
_MAX_AUDIT_DURATION_MS = 86_400_000
_MAX_AUDIT_METADATA_VALUES = 16
_MAX_AUDIT_TRACE_INTEGER = 1_000_000
_AUDIT_TRACE_FIELDS = frozenset(
    {
        "action",
        "content_changed",
        "detail_digest",
        "elements_changed",
        "executed",
        "no_progress_count",
        "outcome",
        "popup_opened",
        "progress",
        "reason_digest",
        "scroll_changed",
        "semantic_execution_count",
        "step",
        "stop_reason",
        "target_present",
        "tier",
        "url_changed",
        "value_present",
        "verified",
    }
)


def _validate_audit_code(value: str, *, field_name: str) -> None:
    if not isinstance(value, str) or not _AUDIT_CODE_PATTERN.fullmatch(value):
        raise ValueError(
            f"Inventory recovery {field_name} must be a bounded machine code"
        )


@dataclass(frozen=True, slots=True)
class InventoryRecoveryTraceEvent:
    """One redacted, machine-readable inventory recovery event.

    Deliberately excluded are page text, URLs, reservation/confirmation identity,
    provider responses, screenshots, cookies, keys, and free-form reasoning.
    """

    kind: str
    fields: tuple[tuple[str, str | bool | int], ...] = ()

    def __post_init__(self) -> None:
        _validate_audit_code(self.kind, field_name="trace kind")
        if not isinstance(self.fields, tuple):
            raise TypeError("Inventory recovery trace fields must be a tuple")
        keys: set[str] = set()
        for pair in self.fields:
            if not isinstance(pair, tuple) or len(pair) != 2:
                raise TypeError("Inventory recovery trace fields must be key/value pairs")
            key, value = pair
            if key not in _AUDIT_TRACE_FIELDS or key in keys:
                raise ValueError("Inventory recovery trace field is not allowlisted")
            keys.add(key)
            if isinstance(value, str):
                _validate_audit_code(value, field_name="trace value")
            elif type(value) is int:
                if not 0 <= value <= _MAX_AUDIT_TRACE_INTEGER:
                    raise ValueError("Inventory recovery trace integer is out of bounds")
            elif type(value) is not bool:
                raise TypeError("Inventory recovery trace values must be safe scalars")

    @classmethod
    def from_mapping(
        cls, event: Mapping[str, str | bool | int]
    ) -> InventoryRecoveryTraceEvent:
        kind = event.get("kind")
        if not isinstance(kind, str):
            raise ValueError("Inventory recovery trace event requires a kind")
        return cls(
            kind=kind,
            fields=tuple(
                sorted((key, value) for key, value in event.items() if key != "kind")
            ),
        )

    def as_dict(self) -> dict[str, str | bool | int]:
        return {"kind": self.kind, **dict(self.fields)}


@dataclass(frozen=True, slots=True)
class InventoryRecoveryAudit:
    """Provider-neutral, content-free audit for one inventory synchronization run."""

    outcome: InventoryRecoveryOutcome
    step: str | None
    providers: tuple[str, ...]
    models: tuple[str, ...]
    roles: tuple[str, ...]
    prompt_versions: tuple[str, ...]
    llm_calls_used: int
    input_tokens: int
    output_tokens: int
    action_count: int
    duration_ms: int
    trace: tuple[InventoryRecoveryTraceEvent, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.outcome, InventoryRecoveryOutcome):
            raise TypeError("Inventory recovery audit outcome is invalid")
        if self.step is not None:
            _validate_audit_code(self.step, field_name="step")
        for field_name, codes in (
            ("providers", self.providers),
            ("models", self.models),
            ("roles", self.roles),
            ("prompt versions", self.prompt_versions),
        ):
            if not isinstance(codes, tuple):
                raise TypeError(f"Inventory recovery {field_name} must be a tuple")
            if len(codes) > _MAX_AUDIT_METADATA_VALUES:
                raise ValueError(
                    f"Inventory recovery {field_name} exceed the bounded limit"
                )
            if len(set(codes)) != len(codes):
                raise ValueError(f"Inventory recovery {field_name} must be unique")
            for code in codes:
                _validate_audit_code(code, field_name=field_name)
        for counter_name, counter, maximum in (
            ("LLM calls", self.llm_calls_used, _MAX_AUDIT_LLM_CALLS),
            ("input tokens", self.input_tokens, _MAX_AUDIT_TOKENS),
            ("output tokens", self.output_tokens, _MAX_AUDIT_TOKENS),
            ("actions", self.action_count, _MAX_AUDIT_ACTIONS),
            ("duration", self.duration_ms, _MAX_AUDIT_DURATION_MS),
        ):
            if type(counter) is not int:
                raise TypeError(
                    f"Inventory recovery {counter_name} must be an integer"
                )
            if not 0 <= counter <= maximum:
                raise ValueError(
                    f"Inventory recovery {counter_name} are out of bounds"
                )
        if not isinstance(self.trace, tuple) or not all(
            isinstance(event, InventoryRecoveryTraceEvent) for event in self.trace
        ):
            raise TypeError("Inventory recovery trace must contain typed events")
        if len(self.trace) > _MAX_AUDIT_TRACE_EVENTS:
            raise ValueError("Inventory recovery trace exceeds the bounded event limit")
        if self.llm_calls_used:
            if not self.providers or not self.models:
                raise ValueError(
                    "Inventory recovery LLM usage requires provider and model metadata"
                )
            if not self.roles or not self.prompt_versions:
                raise ValueError(
                    "Inventory recovery LLM usage requires role and prompt metadata"
                )
        elif any(
            (
                bool(self.providers),
                bool(self.models),
                bool(self.roles),
                bool(self.prompt_versions),
                self.input_tokens != 0,
                self.output_tokens != 0,
            )
        ):
            raise ValueError(
                "Inventory recovery without LLM calls cannot carry provider usage metadata"
            )

        if self.outcome is InventoryRecoveryOutcome.NOT_NEEDED:
            if self.step is not None or self.trace or self.action_count or self.duration_ms:
                raise ValueError(
                    "Inventory recovery not-needed audit cannot carry recovery activity"
                )
        elif self.step is None:
            raise ValueError("Inventory recovery activity requires a named step")

    @classmethod
    def from_operational_events(
        cls,
        *,
        outcome: InventoryRecoveryOutcome,
        step: str | None,
        providers: tuple[str, ...],
        models: tuple[str, ...],
        roles: tuple[str, ...],
        prompt_versions: tuple[str, ...],
        llm_calls_used: int,
        input_tokens: int,
        output_tokens: int,
        action_count: int,
        duration_ms: int,
        operational_events: tuple[Mapping[str, str | bool | int], ...],
    ) -> InventoryRecoveryAudit:
        return cls(
            outcome=outcome,
            step=step,
            providers=providers,
            models=models,
            roles=roles,
            prompt_versions=prompt_versions,
            llm_calls_used=llm_calls_used,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            action_count=action_count,
            duration_ms=duration_ms,
            trace=tuple(
                InventoryRecoveryTraceEvent.from_mapping(event)
                for event in operational_events
            ),
        )


@dataclass(frozen=True, slots=True)
class ReservationObservation:
    remote_id: str
    lifecycle: ReservationLifecycle
    observed_at: datetime
    confirmation_id: str | None = None
    property_name: str | None = None
    property_ref: str | None = None
    check_in: date | None = None
    check_out: date | None = None
    room_type: str | None = None
    booked_total: Money | None = None
    refundable: bool | None = None
    refund_note: str = ""
    refund_deadline: date | None = None
    occupancy: Occupancy | None = None
    source_url: str = ""
    extraction_method: str = "dom"

    def __post_init__(self) -> None:
        if not self.remote_id.strip():
            raise ValueError("Remote reservation identity must be non-empty")
        if self.check_in is not None and self.check_out is not None:
            if self.check_out <= self.check_in:
                raise ValueError("Reservation check-out must be after check-in")


@dataclass(frozen=True, slots=True)
class InventoryDiscoveryResult:
    observations: tuple[ReservationObservation, ...]
    completeness: InventoryCompleteness
    failure_code: SynchronizationFailureCode | None = None
    failure_detail: str | None = None
    recovery_outcome: InventoryRecoveryOutcome = InventoryRecoveryOutcome.NOT_NEEDED
    recovery_step: str | None = None
    recovery_detail: str | None = None
    llm_calls_used: int = 0

    def __post_init__(self) -> None:
        if self.completeness is InventoryCompleteness.FAILED and self.failure_code is None:
            raise ValueError("Failed inventory discovery requires a failure code")
        if self.completeness is InventoryCompleteness.COMPLETE and self.failure_code is not None:
            raise ValueError("Complete discovery cannot carry a failure code")
        if self.llm_calls_used < 0:
            raise ValueError("Inventory LLM call usage cannot be negative")

    @classmethod
    def failed(
        cls, code: SynchronizationFailureCode, detail: str
    ) -> InventoryDiscoveryResult:
        return cls((), InventoryCompleteness.FAILED, code, detail)


@dataclass(frozen=True, slots=True)
class EligibilityDecision:
    status: EligibilityStatus
    reasons: tuple[EligibilityReason, ...]

    @property
    def is_eligible(self) -> bool:
        return self.status is EligibilityStatus.ELIGIBLE


@dataclass(frozen=True, slots=True)
class AccountReservation:
    account_reservation_id: str
    user_id: int
    remote_key_hash: str
    observation: ReservationObservation
    eligibility: EligibilityDecision
    monitoring_booking_id: str | None
    first_observed_at: datetime
    last_observed_at: datetime
    snapshot_revision: int


@dataclass(frozen=True, slots=True)
class SynchronizationReport:
    run_id: str
    completeness: InventoryCompleteness
    discovered: int
    eligible: int
    ineligible: int
    failure_code: SynchronizationFailureCode | None = None
    failure_detail: str | None = None
    recovery_outcome: InventoryRecoveryOutcome = InventoryRecoveryOutcome.NOT_NEEDED
    recovery_step: str | None = None
    recovery_detail: str | None = None
    llm_calls_used: int = 0
    recovery_audit: InventoryRecoveryAudit | None = None

    @property
    def succeeded(self) -> bool:
        return self.completeness is InventoryCompleteness.COMPLETE

    @property
    def assisted(self) -> bool:
        return self.recovery_outcome in {
            InventoryRecoveryOutcome.RECOVERED,
            InventoryRecoveryOutcome.PARTIAL,
        }


def remote_key_hash(user_id: int, remote_id: str) -> str:
    material = f"{user_id}\0{remote_id.strip()}".encode()
    return hashlib.sha256(material).hexdigest()


def evaluate_eligibility(
    observation: ReservationObservation, *, today: date | None = None
) -> EligibilityDecision:
    current_date = today or datetime.now(UTC).date()
    reasons: list[EligibilityReason] = []

    if observation.lifecycle is ReservationLifecycle.ABSENT:
        reasons.append(EligibilityReason.NOT_OBSERVED)
    elif observation.lifecycle is ReservationLifecycle.CANCELLED:
        reasons.append(EligibilityReason.CANCELLED)
    elif observation.lifecycle is ReservationLifecycle.COMPLETED:
        reasons.append(EligibilityReason.PAST_OR_COMPLETED)
    elif observation.lifecycle is not ReservationLifecycle.UPCOMING:
        reasons.append(EligibilityReason.NOT_UPCOMING)

    if observation.check_out is not None and observation.check_out <= current_date:
        _append_once(reasons, EligibilityReason.PAST_OR_COMPLETED)
    if observation.refundable is False:
        reasons.append(EligibilityReason.NON_REFUNDABLE)
    elif observation.refundable is None:
        reasons.append(EligibilityReason.REFUNDABILITY_UNKNOWN)
    if not observation.confirmation_id:
        reasons.append(EligibilityReason.MISSING_CONFIRMATION)
    if not observation.property_name or not observation.property_ref:
        reasons.append(EligibilityReason.MISSING_PROPERTY)
    if observation.check_in is None or observation.check_out is None:
        reasons.append(EligibilityReason.MISSING_STAY_DATES)
    if not observation.room_type:
        reasons.append(EligibilityReason.MISSING_ROOM_TYPE)
    if observation.occupancy is None:
        reasons.append(EligibilityReason.MISSING_OCCUPANCY)
    if observation.booked_total is None:
        reasons.append(EligibilityReason.MISSING_BOOKED_TOTAL)

    return EligibilityDecision(
        EligibilityStatus.ELIGIBLE if not reasons else EligibilityStatus.INELIGIBLE,
        tuple(reasons),
    )


def _append_once(
    reasons: list[EligibilityReason], reason: EligibilityReason
) -> None:
    if reason not in reasons:
        reasons.append(reason)
