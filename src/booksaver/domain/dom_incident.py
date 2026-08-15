"""Content-free domain model for DOM-drift incident operations."""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum

from booksaver.domain.browser_resilience import (
    DomJourney,
    DomStepId,
    TerminalBrowserReason,
)
from booksaver.domain.model_policy import (
    OPUS_5_MODEL,
    SONNET_5_MODEL,
    EscalationTrigger,
    ModelAttemptOutcome,
    ModelProvider,
    ModelRole,
    ReservationStatus,
)

_HEX_64 = re.compile(r"^[0-9a-f]{64}$")
_SAFE_CODE = re.compile(r"^[a-z0-9][a-z0-9._:-]{0,127}$")
MAX_DIAGNOSTIC_IMAGE_BYTES = 512 * 1024


class IncidentState(Enum):
    OBSERVING = "observing"
    OPEN = "open"
    RESOLVED = "resolved"


class IncidentSeverity(Enum):
    OBSERVING = "observing"
    MAINTENANCE_REQUIRED = "maintenance_required"


class DeliveryState(Enum):
    PENDING = "pending"
    IN_FLIGHT = "in_flight"
    DELIVERED = "delivered"
    RETRYABLE_FAILED = "retryable_failed"
    FAILED = "failed"
    DELIVERY_UNKNOWN = "delivery_unknown"
    SUPPRESSED = "suppressed"


class DeliveryFailureCode(Enum):
    OWNER_NOT_CONFIGURED = "owner_not_configured"
    RATE_LIMITED = "rate_limited"
    TRANSPORT_UNAVAILABLE = "transport_unavailable"
    PROVIDER_REJECTED = "provider_rejected"
    RETRIES_EXHAUSTED = "retries_exhausted"


class EvidenceState(Enum):
    PENDING = "pending"
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    EXPIRED = "expired"
    PURGED = "purged"
    CORRUPT = "corrupt"
    UNDECRYPTABLE = "undecryptable"
    OVERSIZED = "oversized"


class IncidentProviderState(Enum):
    COMPLETED = "completed"
    FAILED = "failed"
    NOT_ATTEMPTED = "not_attempted"


class IncidentBudgetState(Enum):
    WITHIN_LIMIT = "within_limit"
    EXHAUSTED = "exhausted"
    NOT_APPLICABLE = "not_applicable"


class IncidentSourceProvenance(Enum):
    SONNET_ASSISTED = "sonnet_assisted"
    OPUS_ASSISTED = "opus_assisted"
    MODEL_DIAGNOSED = "model_diagnosed"
    CODE_MAINTENANCE_REQUIRED = "code_maintenance_required"


def _require_utc(value: datetime, field: str) -> None:
    if value.tzinfo is None or value.utcoffset() != timedelta(0):
        raise ValueError(f"{field} must be a timezone-aware UTC datetime")


def _require_safe_code(value: str, field: str) -> None:
    if not _SAFE_CODE.fullmatch(value):
        raise ValueError(f"{field} must be a bounded machine code")


@dataclass(frozen=True, slots=True)
class StructuralDigest:
    value: str

    def __post_init__(self) -> None:
        if not _HEX_64.fullmatch(self.value):
            raise ValueError("structural digest must be 64 lowercase hexadecimal characters")


@dataclass(frozen=True, slots=True)
class DomDriftFingerprint:
    value: str

    def __post_init__(self) -> None:
        if not _HEX_64.fullmatch(self.value):
            raise ValueError("DOM-drift fingerprint must be 64 lowercase hexadecimal characters")


@dataclass(frozen=True, slots=True)
class DomDriftOccurrence:
    fingerprint: DomDriftFingerprint
    journey: DomJourney
    step_id: DomStepId
    terminal_reason: TerminalBrowserReason
    verifier_category: str
    structural_digest: StructuralDigest
    model_roles: tuple[ModelRole, ...]
    provenance: IncidentSourceProvenance
    provider_state: IncidentProviderState
    budget_state: IncidentBudgetState
    recovered: bool
    observed_at: datetime

    def __post_init__(self) -> None:
        _require_safe_code(self.verifier_category, "verifier_category")
        _require_utc(self.observed_at, "observed_at")
        model_free_maintenance = (
            self.provenance is IncidentSourceProvenance.CODE_MAINTENANCE_REQUIRED
            and self.provider_state is IncidentProviderState.NOT_ATTEMPTED
            and self.budget_state is IncidentBudgetState.NOT_APPLICABLE
            and self.terminal_reason is TerminalBrowserReason.CODE_MAINTENANCE_REQUIRED
        )
        if not self.model_roles and not model_free_maintenance:
            raise ValueError(
                "an incident occurrence requires a model role unless code maintenance is model-free"
            )
        if len(set(self.model_roles)) != len(self.model_roles):
            raise ValueError("model roles must be ordered and unique")


@dataclass(frozen=True, slots=True)
class DomDriftIncident:
    incident_id: uuid.UUID
    fingerprint: DomDriftFingerprint
    journey: DomJourney
    step_id: DomStepId
    terminal_reason: TerminalBrowserReason
    verifier_category: str
    structural_digest: StructuralDigest
    model_roles: tuple[ModelRole, ...]
    provider_state: IncidentProviderState
    budget_state: IncidentBudgetState
    provenance: IncidentSourceProvenance
    state: IncidentState
    severity: IncidentSeverity
    recovered: bool
    occurrence_count: int
    window_occurrence_count: int
    first_observed_at: datetime
    last_observed_at: datetime
    opened_at: datetime | None
    resolved_at: datetime | None
    alert_suppressed_until: datetime | None
    evidence_state: EvidenceState

    def __post_init__(self) -> None:
        _require_safe_code(self.verifier_category, "verifier_category")
        for field, value in (
            ("first_observed_at", self.first_observed_at),
            ("last_observed_at", self.last_observed_at),
            ("opened_at", self.opened_at),
            ("resolved_at", self.resolved_at),
            ("alert_suppressed_until", self.alert_suppressed_until),
        ):
            if value is not None:
                _require_utc(value, field)
        if self.occurrence_count < 1 or self.window_occurrence_count < 1:
            raise ValueError("incident occurrence counts must be positive")
        if self.window_occurrence_count > self.occurrence_count:
            raise ValueError("window occurrence count cannot exceed the total")
        if self.last_observed_at < self.first_observed_at:
            raise ValueError("last occurrence cannot precede first occurrence")
        if self.state is IncidentState.OPEN and self.opened_at is None:
            raise ValueError("an open incident requires opened_at")
        if self.state is IncidentState.RESOLVED and self.resolved_at is None:
            raise ValueError("a resolved incident requires resolved_at")


@dataclass(frozen=True, slots=True)
class IncidentAlert:
    alert_id: uuid.UUID
    incident_id: uuid.UUID
    generation: int
    severity: IncidentSeverity
    delivery_state: DeliveryState
    attempt_count: int
    next_attempt_at: datetime | None
    claimed_at: datetime | None
    delivered_at: datetime | None
    failure_code: DeliveryFailureCode | None

    def __post_init__(self) -> None:
        if self.generation < 1 or self.attempt_count < 0:
            raise ValueError("alert generation must be positive and attempts non-negative")
        for field, value in (
            ("next_attempt_at", self.next_attempt_at),
            ("claimed_at", self.claimed_at),
            ("delivered_at", self.delivered_at),
        ):
            if value is not None:
                _require_utc(value, field)


@dataclass(frozen=True, slots=True)
class OwnerIncidentNotice:
    incident_id: uuid.UUID
    journey: DomJourney
    step_id: DomStepId
    category: TerminalBrowserReason
    recovered: bool
    occurrence_count: int
    model_roles: tuple[ModelRole, ...]
    provider_state: IncidentProviderState
    budget_state: IncidentBudgetState
    evidence_state: EvidenceState

    def __post_init__(self) -> None:
        if self.occurrence_count < 1:
            raise ValueError("notice occurrence count must be positive")


@dataclass(frozen=True, slots=True)
class DiagnosticModelAttempt:
    """Closed, identifier-free projection of one admitted model attempt."""

    ordinal: int
    provider: ModelProvider
    model: str
    role: ModelRole
    trigger: EscalationTrigger
    outcome: ModelAttemptOutcome | None
    status: ReservationStatus
    input_tokens: int | None
    output_tokens: int | None
    latency_ms: int | None
    reserved_micro_usd: int
    charged_micro_usd: int | None

    def __post_init__(self) -> None:
        if isinstance(self.ordinal, bool) or self.ordinal < 1:
            raise ValueError("diagnostic attempt ordinal must be positive")
        if not isinstance(self.provider, ModelProvider):
            raise ValueError("diagnostic attempt provider must use the closed vocabulary")
        if self.model not in {SONNET_5_MODEL, OPUS_5_MODEL}:
            raise ValueError("diagnostic attempt model must be an approved model identity")
        if not isinstance(self.role, ModelRole):
            raise ValueError("diagnostic attempt role must use the closed vocabulary")
        if not isinstance(self.trigger, EscalationTrigger):
            raise ValueError("diagnostic attempt trigger must use the closed vocabulary")
        if self.outcome is not None and not isinstance(self.outcome, ModelAttemptOutcome):
            raise ValueError("diagnostic attempt outcome must use the closed vocabulary")
        if not isinstance(self.status, ReservationStatus):
            raise ValueError("diagnostic attempt status must use the closed vocabulary")
        if (self.input_tokens is None) != (self.output_tokens is None):
            raise ValueError("diagnostic attempt token counts must be present together")
        for field, value in (
            ("input_tokens", self.input_tokens),
            ("output_tokens", self.output_tokens),
            ("latency_ms", self.latency_ms),
            ("reserved_micro_usd", self.reserved_micro_usd),
            ("charged_micro_usd", self.charged_micro_usd),
        ):
            if value is not None and (isinstance(value, bool) or value < 0):
                raise ValueError(f"diagnostic attempt {field} cannot be negative")


@dataclass(frozen=True, slots=True)
class DiagnosticBundle:
    """Sanitized incident evidence that is legal only inside ciphertext."""

    incident_id: uuid.UUID
    source_user_ids: tuple[int, ...]
    structural_roles: tuple[str, ...]
    action_outcomes: tuple[str, ...]
    terminal_reason: TerminalBrowserReason
    model_roles: tuple[ModelRole, ...]
    provider_state: IncidentProviderState
    budget_state: IncidentBudgetState
    created_at: datetime
    model_attempts: tuple[DiagnosticModelAttempt, ...] = ()
    structural_image: bytes | None = None
    version: int = 1

    def __post_init__(self) -> None:
        _require_utc(self.created_at, "created_at")
        if self.version != 1:
            raise ValueError("unsupported diagnostic bundle version")
        if not self.source_user_ids or any(value < 1 for value in self.source_user_ids):
            raise ValueError("diagnostic source users must be positive local IDs")
        if len(set(self.source_user_ids)) != len(self.source_user_ids):
            raise ValueError("diagnostic source users must be unique")
        if len(self.structural_roles) > 128 or len(self.action_outcomes) > 128:
            raise ValueError("diagnostic structural data exceeds bounded item count")
        for value in (*self.structural_roles, *self.action_outcomes):
            _require_safe_code(value, "diagnostic item")
        if self.model_attempts:
            ordinals = tuple(attempt.ordinal for attempt in self.model_attempts)
            if ordinals != tuple(sorted(set(ordinals))):
                raise ValueError("diagnostic model attempts must be strictly ordered and unique")
            attempt_roles = tuple(dict.fromkeys(attempt.role for attempt in self.model_attempts))
            if attempt_roles != self.model_roles:
                raise ValueError("diagnostic model roles must match the ordered attempt projection")
        if self.structural_image is not None and (
            len(self.structural_image) == 0
            or len(self.structural_image) > MAX_DIAGNOSTIC_IMAGE_BYTES
        ):
            raise ValueError("diagnostic structural image exceeds its size bound")


@dataclass(frozen=True, slots=True)
class IncidentDraft:
    """Ephemeral handoff captured before browser cleanup and persisted afterward."""

    occurrence: DomDriftOccurrence
    diagnostic_bundle: DiagnosticBundle | None = None

    def __post_init__(self) -> None:
        if self.diagnostic_bundle is not None and self.diagnostic_bundle.incident_id.int != 0:
            raise ValueError(
                "an incident draft bundle must use the zero UUID until correlation assigns an ID"
            )


@dataclass(frozen=True, slots=True)
class DiagnosticInspection:
    evidence_state: EvidenceState
    bundle: DiagnosticBundle | None = None


@dataclass(frozen=True, slots=True)
class DiagnosticPurgeResult:
    deleted_matching: int = 0
    deleted_unverifiable: int = 0

    @property
    def total_deleted(self) -> int:
        return self.deleted_matching + self.deleted_unverifiable
