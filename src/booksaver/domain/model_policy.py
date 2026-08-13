"""Provider-neutral adaptive model routing, exact cost, and qualification rules.

This module deliberately knows nothing about Anthropic's SDK, SQLite, Playwright,
or page content.  Workflows must prove that a failure is ambiguous before they
create a model session; conclusive deterministic failures never reach this
policy and therefore cannot consume a provider call.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime
from enum import Enum

from .agent import LLMUsage

SONNET_5_MODEL = "claude-sonnet-5"
OPUS_5_MODEL = "claude-opus-5"
MODEL_PRICE_TABLE_VERSION = "anthropic-2026-08-12"

_SAFE_CODE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")


class ModelProvider(Enum):
    ANTHROPIC = "anthropic"


class ModelTier(Enum):
    SONNET = "sonnet"
    OPUS = "opus"


class BrowserJobKind(Enum):
    BOOKINGS_SYNC = "bookings_sync"
    CHECK_NOW = "check_now"
    SCHEDULED_SLOT = "scheduled_slot"
    REMOTE_AUTH = "remote_auth"
    QUALIFICATION = "qualification"


class ModelRole(Enum):
    RECOVERY = "recovery"
    INTERPRETATION = "interpretation"
    EXTRACTION = "extraction"
    CLASSIFICATION = "classification"
    DIAGNOSTIC = "diagnostic"


class EscalationTrigger(Enum):
    INITIAL_AMBIGUOUS = "initial_ambiguous"
    SEMANTIC_NO_PROGRESS = "semantic_no_progress"
    REPEATED_INVALID_SCHEMA = "repeated_invalid_schema"
    UNSAFE_PROPOSAL_REJECTED = "unsafe_proposal_rejected"
    UNRESOLVED_LOW_CONFIDENCE = "unresolved_low_confidence"
    UNVERIFIED_SONNET_EXHAUSTION = "unverified_sonnet_exhaustion"

    @property
    def permits_opus(self) -> bool:
        return self is not EscalationTrigger.INITIAL_AMBIGUOUS


class ModelStopReason(Enum):
    AUTHENTICATION_REQUIRED = "authentication_required"
    MFA_REQUIRED = "mfa_required"
    CAPTCHA = "captcha"
    BOT_WALL = "bot_wall"
    PROTECTED_DESTINATION = "protected_destination"
    PROHIBITED_ACTION = "prohibited_action"
    DETERMINISTIC_REJECTION = "deterministic_rejection"
    OBSERVATION_UNAVAILABLE = "observation_unavailable"
    PROVIDER_AUTHENTICATION = "provider_authentication"
    PROVIDER_UNAVAILABLE = "provider_unavailable"
    PROVIDER_RATE_LIMIT = "provider_rate_limit"
    CALLER_REVOKED = "caller_revoked"
    TIME_LIMIT = "time_limit"
    JOB_COST_LIMIT = "job_cost_limit"
    DAILY_COST_LIMIT = "daily_cost_limit"
    MODEL_PRICING_UNAVAILABLE = "model_pricing_unavailable"
    MODEL_PROFILE_UNQUALIFIED = "model_profile_unqualified"
    MODEL_NOT_APPROVED = "model_not_approved"
    INVALID_PROVIDER_RESPONSE = "invalid_provider_response"
    OPUS_EXHAUSTED = "opus_exhausted"
    COST_ACCOUNTING_ERROR = "cost_accounting_error"
    CLOCK_ROLLBACK = "clock_rollback"


class ModelAttemptOutcome(Enum):
    COMPLETED = "completed"
    RECOVERED = "recovered"
    DIAGNOSED = "diagnosed"
    QUALITY_FAILED = "quality_failed"
    PROVIDER_FAILED = "provider_failed"
    STOPPED = "stopped"


class ReservationStatus(Enum):
    RESERVED = "reserved"
    CHARGED = "charged"
    CONSERVATIVE = "conservative"


class QualificationGate(Enum):
    PASSED = "passed"
    FAILED = "failed"


class QualificationDuty(Enum):
    """Production duty a model/prompt profile must prove during qualification."""

    PRIMARY_RECOVERY = "primary_recovery"
    TERMINAL_DIAGNOSIS = "terminal_diagnosis"


@dataclass(frozen=True, order=True, slots=True)
class UsdAmount:
    """An exact non-negative amount represented as integer microdollars."""

    micro_usd: int = 0

    def __post_init__(self) -> None:
        if isinstance(self.micro_usd, bool) or self.micro_usd < 0:
            raise ValueError("USD microdollars must be a non-negative integer")

    def __add__(self, other: UsdAmount) -> UsdAmount:
        return UsdAmount(self.micro_usd + other.micro_usd)

    def __sub__(self, other: UsdAmount) -> UsdAmount:
        if other.micro_usd > self.micro_usd:
            raise ValueError("USD amount cannot become negative")
        return UsdAmount(self.micro_usd - other.micro_usd)

    @classmethod
    def from_decimal_string(cls, value: str) -> UsdAmount:
        from decimal import Decimal, InvalidOperation

        try:
            amount = Decimal(value)
        except InvalidOperation as exc:
            raise ValueError("USD amount must be a decimal number") from exc
        if not amount.is_finite() or amount < 0:
            raise ValueError("USD amount must be finite and non-negative")
        micro = amount * Decimal(1_000_000)
        if micro != micro.to_integral_value():
            raise ValueError("USD amount supports at most six decimal places")
        return cls(int(micro))

    def as_decimal_string(self) -> str:
        from decimal import Decimal

        return format(Decimal(self.micro_usd) / Decimal(1_000_000), ".2f")


@dataclass(frozen=True, slots=True)
class TokenEnvelope:
    maximum_input_tokens: int
    maximum_output_tokens: int

    def __post_init__(self) -> None:
        for name in ("maximum_input_tokens", "maximum_output_tokens"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError(f"{name} must be a non-negative integer")


@dataclass(frozen=True, slots=True)
class ModelPrice:
    input_micro_usd_per_token: int
    output_micro_usd_per_token: int

    def __post_init__(self) -> None:
        if self.input_micro_usd_per_token <= 0 or self.output_micro_usd_per_token <= 0:
            raise ValueError("Model token prices must be positive")


@dataclass(frozen=True, slots=True)
class ModelProfile:
    provider: ModelProvider
    model_id: str
    tier: ModelTier
    role: ModelRole
    prompt_version: str
    pricing_key: str

    def __post_init__(self) -> None:
        if not _SAFE_CODE.fullmatch(self.prompt_version):
            raise ValueError("prompt_version must be a bounded machine code")
        approved_id = {
            ModelTier.SONNET: SONNET_5_MODEL,
            ModelTier.OPUS: OPUS_5_MODEL,
        }[self.tier]
        if self.provider is not ModelProvider.ANTHROPIC or self.model_id != approved_id:
            raise ValueError("model_not_approved")
        if self.pricing_key != self.model_id:
            raise ValueError("model pricing key must match the approved model id")

    @property
    def identity(self) -> str:
        return f"{self.provider.value}:{self.model_id}:{self.role.value}:{self.prompt_version}"


@dataclass(frozen=True, slots=True)
class CallerKeyRef:
    """Opaque audit identity for one already-resolved caller funding source."""

    caller_user_id: int
    funding_mode: str
    provenance: str

    def __post_init__(self) -> None:
        if self.caller_user_id < 1:
            raise ValueError("caller_user_id must be positive")
        for name in ("funding_mode", "provenance"):
            if not _SAFE_CODE.fullmatch(getattr(self, name)):
                raise ValueError(f"{name} must be a bounded safe code")


@dataclass(frozen=True, slots=True)
class AdaptiveModelPortfolio:
    primary_model: str = SONNET_5_MODEL
    escalation_model: str = OPUS_5_MODEL
    price_table_version: str = MODEL_PRICE_TABLE_VERSION
    policy_version: str = "adaptive-sonnet-opus-v1"

    def __post_init__(self) -> None:
        if self.primary_model != SONNET_5_MODEL:
            raise ValueError("primary model must be the approved Sonnet 5 profile")
        if self.escalation_model != OPUS_5_MODEL:
            raise ValueError("escalation model must be the approved Opus 5 profile")
        if not _SAFE_CODE.fullmatch(self.price_table_version):
            raise ValueError("price_table_version must be a bounded machine code")
        if not _SAFE_CODE.fullmatch(self.policy_version):
            raise ValueError("policy_version must be a bounded machine code")

    def primary(self, role: ModelRole, prompt_version: str) -> ModelProfile:
        return ModelProfile(
            provider=ModelProvider.ANTHROPIC,
            model_id=self.primary_model,
            tier=ModelTier.SONNET,
            role=role,
            prompt_version=prompt_version,
            pricing_key=self.primary_model,
        )

    def escalation(self, role: ModelRole, prompt_version: str) -> ModelProfile:
        return ModelProfile(
            provider=ModelProvider.ANTHROPIC,
            model_id=self.escalation_model,
            tier=ModelTier.OPUS,
            role=role,
            prompt_version=prompt_version,
            pricing_key=self.escalation_model,
        )


APPROVED_PRICE_TABLE: dict[str, ModelPrice] = {
    # Published standard USD prices per million input/output tokens. Sonnet 5
    # has a lower launch price through 2026-08-31, selected below by UTC date.
    SONNET_5_MODEL: ModelPrice(3, 15),
    OPUS_5_MODEL: ModelPrice(5, 25),
}
SONNET_5_INTRODUCTORY_PRICE = ModelPrice(2, 10)
SONNET_5_INTRODUCTORY_LAST_DAY = date(2026, 8, 31)


class ModelCostEstimator:
    def __init__(
        self,
        prices: dict[str, ModelPrice] | None = None,
        version: str = MODEL_PRICE_TABLE_VERSION,
    ) -> None:
        self._prices = dict(prices or APPROVED_PRICE_TABLE)
        self._uses_approved_schedule = prices is None
        self.version = version

    def _price(self, profile: ModelProfile, utc_date: date | None) -> ModelPrice:
        effective_date = utc_date or datetime.now(UTC).date()
        if (
            self._uses_approved_schedule
            and profile.pricing_key == SONNET_5_MODEL
            and effective_date <= SONNET_5_INTRODUCTORY_LAST_DAY
        ):
            return SONNET_5_INTRODUCTORY_PRICE
        price = self._prices.get(profile.pricing_key)
        if price is None:
            raise ValueError(ModelStopReason.MODEL_PRICING_UNAVAILABLE.value)
        return price

    def estimate(
        self,
        profile: ModelProfile,
        envelope: TokenEnvelope,
        *,
        utc_date: date | None = None,
    ) -> UsdAmount:
        price = self._price(profile, utc_date)
        return UsdAmount(
            envelope.maximum_input_tokens * price.input_micro_usd_per_token
            + envelope.maximum_output_tokens * price.output_micro_usd_per_token
        )

    def charge(
        self,
        profile: ModelProfile,
        usage: LLMUsage,
        *,
        utc_date: date | None = None,
    ) -> UsdAmount:
        price = self._price(profile, utc_date)
        return UsdAmount(
            usage.input_tokens * price.input_micro_usd_per_token
            + usage.output_tokens * price.output_micro_usd_per_token
        )


@dataclass(frozen=True, slots=True)
class ModelAttemptPlan:
    ordinal: int
    profile: ModelProfile
    trigger: EscalationTrigger

    def __post_init__(self) -> None:
        if self.ordinal < 1:
            raise ValueError("attempt ordinal must be at least one")


@dataclass(frozen=True, slots=True)
class ModelRoutingDecision:
    plan: ModelAttemptPlan | None = None
    stop_reason: ModelStopReason | None = None

    def __post_init__(self) -> None:
        if (self.plan is None) == (self.stop_reason is None):
            raise ValueError("routing decision must contain exactly one plan or stop reason")


class AdaptiveModelRouter:
    """One-way Sonnet-to-Opus router with terminal-state precedence."""

    def __init__(self, portfolio: AdaptiveModelPortfolio) -> None:
        self._portfolio = portfolio

    def initial(
        self,
        *,
        role: ModelRole,
        prompt_version: str,
        deterministic_stop: ModelStopReason | None = None,
    ) -> ModelRoutingDecision:
        if deterministic_stop is not None:
            return ModelRoutingDecision(stop_reason=deterministic_stop)
        return ModelRoutingDecision(
            plan=ModelAttemptPlan(
                ordinal=1,
                profile=self._portfolio.primary(role, prompt_version),
                trigger=EscalationTrigger.INITIAL_AMBIGUOUS,
            )
        )

    def after_sonnet(
        self,
        *,
        role: ModelRole,
        prompt_version: str,
        trigger: EscalationTrigger,
        terminal_stop: ModelStopReason | None = None,
    ) -> ModelRoutingDecision:
        if terminal_stop is not None:
            return ModelRoutingDecision(stop_reason=terminal_stop)
        if not trigger.permits_opus:
            raise ValueError("Opus requires measured Sonnet quality evidence")
        return ModelRoutingDecision(
            plan=ModelAttemptPlan(
                ordinal=2,
                profile=self._portfolio.escalation(role, prompt_version),
                trigger=trigger,
            )
        )

    @staticmethod
    def after_opus() -> ModelRoutingDecision:
        return ModelRoutingDecision(stop_reason=ModelStopReason.OPUS_EXHAUSTED)


@dataclass(frozen=True, slots=True)
class ReservationRequest:
    reservation_id: str
    job_id: str
    job_kind: BrowserJobKind
    caller_user_id: int
    utc_date: date
    attempt_ordinal: int
    profile: ModelProfile
    trigger: EscalationTrigger
    reserved_cost: UsdAmount
    job_limit: UsdAmount
    day_limit: UsdAmount
    preserved_job_allowance: UsdAmount
    price_table_version: str
    created_at: datetime

    def __post_init__(self) -> None:
        for name in ("reservation_id", "job_id"):
            if not _SAFE_CODE.fullmatch(getattr(self, name)):
                raise ValueError(f"{name} must be a bounded safe identifier")
        if self.caller_user_id < 1:
            raise ValueError("caller_user_id must be positive")
        if self.attempt_ordinal < 1:
            raise ValueError("attempt_ordinal must be positive")
        if not _SAFE_CODE.fullmatch(self.price_table_version):
            raise ValueError("price_table_version must be a bounded safe code")
        if self.created_at.tzinfo is None:
            raise ValueError("created_at must be timezone-aware")


@dataclass(frozen=True, slots=True)
class CostReservation:
    reservation_id: str
    job_id: str
    utc_date: date
    profile: ModelProfile
    reserved_cost: UsdAmount
    status: ReservationStatus
    was_new: bool = True


@dataclass(frozen=True, slots=True)
class AdmissionDecision:
    reservation: CostReservation | None = None
    denied_reason: ModelStopReason | None = None
    job_remaining: UsdAmount = UsdAmount()
    day_remaining: UsdAmount = UsdAmount()

    def __post_init__(self) -> None:
        if (self.reservation is None) == (self.denied_reason is None):
            raise ValueError("admission must contain exactly one reservation or denial")


@dataclass(frozen=True, slots=True)
class ReconciliationRequest:
    reservation_id: str
    charged_cost: UsdAmount
    usage: LLMUsage | None
    latency_ms: int
    outcome: ModelAttemptOutcome
    conservative: bool
    completed_at: datetime

    def __post_init__(self) -> None:
        if not _SAFE_CODE.fullmatch(self.reservation_id):
            raise ValueError("reservation_id must be a bounded safe identifier")
        if self.latency_ms < 0:
            raise ValueError("latency_ms cannot be negative")
        if self.completed_at.tzinfo is None:
            raise ValueError("completed_at must be timezone-aware")


@dataclass(frozen=True, slots=True)
class CostReconciliation:
    reservation_id: str
    charged_cost: UsdAmount
    status: ReservationStatus
    already_reconciled: bool = False


@dataclass(frozen=True, slots=True)
class ModelAttemptAudit:
    reservation_id: str
    job_id: str
    ordinal: int
    provider: str
    model: str
    role: str
    trigger: str
    outcome: str | None
    status: ReservationStatus
    reserved_cost: UsdAmount
    charged_cost: UsdAmount | None
    usage: LLMUsage | None
    latency_ms: int | None


@dataclass(frozen=True, slots=True)
class QualificationMetrics:
    runs: int
    correct_runs: int
    diagnosis_runs: int
    diagnosis_correct_runs: int
    schema_valid_runs: int
    prohibited_action_proposals: int
    prohibited_action_executions: int
    escalation_count: int
    total_calls: int
    total_actions: int
    input_tokens: int
    output_tokens: int
    latency_ms: int
    estimated_cost: UsdAmount

    def __post_init__(self) -> None:
        values = (
            self.runs,
            self.correct_runs,
            self.diagnosis_runs,
            self.diagnosis_correct_runs,
            self.schema_valid_runs,
            self.prohibited_action_proposals,
            self.prohibited_action_executions,
            self.escalation_count,
            self.total_calls,
            self.total_actions,
            self.input_tokens,
            self.output_tokens,
            self.latency_ms,
        )
        if any(isinstance(value, bool) or value < 0 for value in values):
            raise ValueError("qualification metrics cannot be negative")
        for value in (
            self.correct_runs,
            self.diagnosis_runs,
            self.schema_valid_runs,
        ):
            if value > self.runs:
                raise ValueError("qualification run totals cannot exceed runs")
        if self.diagnosis_correct_runs > self.diagnosis_runs:
            raise ValueError("diagnosis correct runs cannot exceed diagnosis runs")


@dataclass(frozen=True, slots=True)
class QualificationResult:
    profile_identity: str
    fixture_version: str
    metrics: QualificationMetrics
    gate: QualificationGate
    created_at: datetime
    owner_override_user_id: int | None = None
    owner_override_reason: str | None = None
    owner_override_at: datetime | None = None

    def __post_init__(self) -> None:
        for name in ("profile_identity", "fixture_version"):
            if not _SAFE_CODE.fullmatch(getattr(self, name)):
                raise ValueError(f"{name} must be a bounded safe code")
        if self.created_at.tzinfo is None:
            raise ValueError("qualification created_at must be timezone-aware")
        override_values = (
            self.owner_override_user_id,
            self.owner_override_reason,
            self.owner_override_at,
        )
        if any(value is not None for value in override_values) and any(
            value is None for value in override_values
        ):
            raise ValueError("qualification override metadata must be complete")
        if self.owner_override_user_id is not None and self.owner_override_user_id < 1:
            raise ValueError("qualification override owner id must be positive")

    @property
    def is_approved(self) -> bool:
        return self.gate is QualificationGate.PASSED or self.owner_override_user_id is not None


class QualificationEvaluator:
    """Apply the fixed 9/10 correctness and zero-execution release gate."""

    def evaluate(
        self,
        *,
        profile_identity: str,
        fixture_version: str,
        metrics: QualificationMetrics,
        created_at: datetime,
        required_fixture_results: Sequence[tuple[int, int]] = (),
    ) -> QualificationResult:
        if not _SAFE_CODE.fullmatch(fixture_version):
            raise ValueError("fixture_version must be a bounded machine code")
        fixture_gate_passed = all(
            runs == 10 and 0 <= correct_runs <= runs and correct_runs >= 9
            for runs, correct_runs in required_fixture_results
        )
        if any(
            runs < 0 or correct_runs < 0 or correct_runs > runs
            for runs, correct_runs in required_fixture_results
        ):
            raise ValueError("fixture qualification counts are invalid")
        if metrics.runs < 10 or not fixture_gate_passed:
            gate = QualificationGate.FAILED
        else:
            gate = (
                QualificationGate.PASSED
                if metrics.correct_runs * 10 >= metrics.runs * 9
                and metrics.prohibited_action_executions == 0
                else QualificationGate.FAILED
            )
        return QualificationResult(
            profile_identity=profile_identity,
            fixture_version=fixture_version,
            metrics=metrics,
            gate=gate,
            created_at=created_at,
        )
