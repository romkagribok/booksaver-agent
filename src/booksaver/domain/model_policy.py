"""Model-attempt vocabulary still read by DOM incidents and stored diagnostics.

BookSaver no longer calls Anthropic models: TypeSafe's Jev is the only model provider.
The enums and model names below stay because DOM-drift incidents and encrypted
diagnostics persisted before that change name them; ``UsdAmount`` is the exact
money type for execution cost caps.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .agent import LLMUsage

# Model names recorded by diagnostics persisted before the Jev-only change.
SONNET_5_MODEL = "claude-sonnet-5"
OPUS_5_MODEL = "claude-opus-5"


class ModelProvider(Enum):
    ANTHROPIC = "anthropic"


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
