from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date, datetime
from enum import Enum
from typing import TYPE_CHECKING

from .mobile_web import PriceSourceProvenance
from .session import SessionMode
from .value_objects import Money

if TYPE_CHECKING:
    from .browser_resilience import TerminalBrowserDiagnosis, TerminalBrowserReason


class CheckOutcome(Enum):
    SUCCESS = "success"
    FAILURE = "failure"


class ExtractionMethod(Enum):
    DOM = "dom"
    LLM = "llm"
    NONE = "none"
    AGENT = "agent"  # bolt 007: any journey step needed LLM-agent takeover


class FailureCode(Enum):
    NAVIGATION_ERROR = "navigation_error"
    AUTH_REQUIRED = "auth_required"
    EXTRACTION_FAILED = "extraction_failed"
    LLM_ERROR = "llm_error"
    TIMEOUT = "timeout"
    UNKNOWN = "unknown"
    # Search-journey codes (bolt 006, ADR-013/014)
    OCCUPANCY_MISSING = "occupancy_missing"
    STEP_FAILED = "step_failed"
    PROPERTY_NOT_FOUND = "property_not_found"
    NO_EQUIVALENT_OFFER = "no_equivalent_offer"
    CURRENCY_MISMATCH = "currency_mismatch"
    BOT_WALL = "bot_wall"
    # Agentic-escalation codes (bolt 007, ADR-015/016/017)
    AGENT_GAVE_UP = "agent_gave_up"
    # Progress-aware recovery (bolt 038, ADR-030): the controller could not
    # verify material progress after its bounded evidence-reorientation policy.
    # Keep this distinct from a model-selected give-up, an exhausted budget,
    # and an LLM/provider failure so operators can diagnose the right layer.
    AGENT_NO_PROGRESS = "agent_no_progress"
    BLOCKED_ACTION = "blocked_action"
    BUDGET_EXCEEDED = "budget_exceeded"
    # Hybrid billing (bolt 009, US-027): the booking owner's personal Anthropic
    # key could not be used (missing encryption key, corrupt ciphertext, or the
    # decrypted key itself was rejected).
    USER_KEY_INVALID = "user_key_invalid"
    # Per-user fair-scheduling code (bolt 010, US-031)
    USER_CHECK_LIMIT_REACHED = "user_check_limit_reached"
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
    COST_ACCOUNTING_ERROR = "cost_accounting_error"
    CLOCK_ROLLBACK = "clock_rollback"
    DOM_AMBIGUITY = "dom_ambiguity"
    DOM_MAINTENANCE_REQUIRED = "dom_maintenance_required"
    INFRASTRUCTURE_FAILURE = "infrastructure_failure"


@dataclass(frozen=True)
class FailureReason:
    code: FailureCode
    detail: str


def failure_code_for_terminal(reason: TerminalBrowserReason) -> FailureCode:
    """Preserve canonical browser stops instead of collapsing to generic codes."""

    from .browser_resilience import TerminalBrowserReason

    exact = {
        TerminalBrowserReason.AUTHENTICATION_REQUIRED: FailureCode.AUTH_REQUIRED,
        TerminalBrowserReason.MFA_REQUIRED: FailureCode.AUTH_REQUIRED,
        TerminalBrowserReason.BOT_WALL: FailureCode.BOT_WALL,
        TerminalBrowserReason.BLOCKED_DESTINATION: FailureCode.BLOCKED_ACTION,
        TerminalBrowserReason.PROHIBITED_ACTION: FailureCode.BLOCKED_ACTION,
        TerminalBrowserReason.OBSERVATION_UNAVAILABLE: FailureCode.OBSERVATION_UNAVAILABLE,
        TerminalBrowserReason.PROVIDER_AUTHENTICATION: FailureCode.PROVIDER_AUTHENTICATION,
        TerminalBrowserReason.PROVIDER_UNAVAILABLE: FailureCode.PROVIDER_UNAVAILABLE,
        TerminalBrowserReason.PROVIDER_RATE_LIMIT: FailureCode.PROVIDER_RATE_LIMIT,
        TerminalBrowserReason.CALLER_REVOKED: FailureCode.CALLER_REVOKED,
        TerminalBrowserReason.TIME_LIMIT: FailureCode.TIME_LIMIT,
        TerminalBrowserReason.JOB_COST_LIMIT: FailureCode.JOB_COST_LIMIT,
        TerminalBrowserReason.DAILY_COST_LIMIT: FailureCode.DAILY_COST_LIMIT,
        TerminalBrowserReason.MODEL_PRICING_UNAVAILABLE: (
            FailureCode.MODEL_PRICING_UNAVAILABLE
        ),
        TerminalBrowserReason.MODEL_PROFILE_UNQUALIFIED: (
            FailureCode.MODEL_PROFILE_UNQUALIFIED
        ),
        TerminalBrowserReason.MODEL_NOT_APPROVED: FailureCode.MODEL_NOT_APPROVED,
        TerminalBrowserReason.INVALID_PROVIDER_RESPONSE: (
            FailureCode.INVALID_PROVIDER_RESPONSE
        ),
        TerminalBrowserReason.COST_ACCOUNTING_ERROR: FailureCode.COST_ACCOUNTING_ERROR,
        TerminalBrowserReason.CLOCK_ROLLBACK: FailureCode.CLOCK_ROLLBACK,
        TerminalBrowserReason.UNRESOLVED_AMBIGUITY: FailureCode.DOM_AMBIGUITY,
        TerminalBrowserReason.CODE_MAINTENANCE_REQUIRED: (
            FailureCode.DOM_MAINTENANCE_REQUIRED
        ),
        TerminalBrowserReason.INFRASTRUCTURE_FAILURE: FailureCode.INFRASTRUCTURE_FAILURE,
        TerminalBrowserReason.CURRENCY_MISMATCH: FailureCode.CURRENCY_MISMATCH,
        TerminalBrowserReason.EXPLICIT_UNAVAILABLE: FailureCode.NO_EQUIVALENT_OFFER,
        TerminalBrowserReason.PROPERTY_CONTEXT_MISMATCH: FailureCode.STEP_FAILED,
        TerminalBrowserReason.CANDIDATES_REJECTED: FailureCode.NO_EQUIVALENT_OFFER,
        TerminalBrowserReason.POPUP_REFUSED: FailureCode.BLOCKED_ACTION,
        TerminalBrowserReason.DETERMINISTIC_REJECTION: FailureCode.STEP_FAILED,
        TerminalBrowserReason.UNSUPPORTED_PAGE: FailureCode.DOM_MAINTENANCE_REQUIRED,
    }
    if reason in {
        TerminalBrowserReason.POSTCONDITION_SATISFIED,
        TerminalBrowserReason.CODE_VERIFICATION_REQUIRED,
    }:
        raise ValueError("a non-terminal browser state has no failure code")
    return exact[reason]


@dataclass(frozen=True)
class RefundIndicators:
    is_refundable: bool | None
    cancellation_deadline: date | None = None
    raw_text: str | None = None


@dataclass(frozen=True)
class ExtractedBookingFields:
    property_name: str | None = None
    room_label: str | None = None
    check_in: date | None = None
    check_out: date | None = None


@dataclass(frozen=True)
class CheckResult:
    check_id: str
    booking_id: str
    checked_at: datetime
    outcome: CheckOutcome
    extraction_method: ExtractionMethod
    live_price: Money | None = None
    refund_indicators: RefundIndicators | None = None
    extracted_fields: ExtractedBookingFields | None = None
    failure_reason: FailureReason | None = None
    # US-035: which session mode produced this result. Deliberately NOT
    # persisted (no check_history column — that schema is owned elsewhere;
    # see search_check_job.py's note) — it only needs to survive the short
    # in-process hop from `run_all_active()` to `SavingsPipeline.process()`
    # within the same scheduler tick, so a savings alert can label a
    # logged-out live price as a public rate.
    session_mode: SessionMode | None = None
    price_source: PriceSourceProvenance | None = None
    terminal_diagnosis: TerminalBrowserDiagnosis | None = None
    assisted_diagnoses: tuple[TerminalBrowserDiagnosis, ...] = ()

    def __post_init__(self) -> None:
        from .browser_resilience import validate_assisted_diagnoses

        validate_assisted_diagnoses(self.assisted_diagnoses)
        if self.outcome is CheckOutcome.SUCCESS and self.live_price is None:
            raise ValueError("A successful check must have a live_price")
        if self.outcome is CheckOutcome.SUCCESS and self.terminal_diagnosis is not None:
            raise ValueError("A successful check cannot carry a terminal diagnosis")
        if self.outcome is CheckOutcome.FAILURE and self.failure_reason is None:
            raise ValueError("A failed check must have a failure_reason")

    @classmethod
    def success(
        cls,
        booking_id: str,
        checked_at: datetime,
        live_price: Money,
        extraction_method: ExtractionMethod,
        refund_indicators: RefundIndicators | None = None,
        extracted_fields: ExtractedBookingFields | None = None,
        session_mode: SessionMode | None = None,
        price_source: PriceSourceProvenance | None = None,
        assisted_diagnoses: tuple[TerminalBrowserDiagnosis, ...] = (),
    ) -> CheckResult:
        return cls(
            check_id=str(uuid.uuid4()),
            booking_id=booking_id,
            checked_at=checked_at,
            outcome=CheckOutcome.SUCCESS,
            extraction_method=extraction_method,
            live_price=live_price,
            refund_indicators=refund_indicators,
            extracted_fields=extracted_fields,
            session_mode=session_mode,
            price_source=price_source,
            assisted_diagnoses=assisted_diagnoses,
        )

    @classmethod
    def failure(
        cls,
        booking_id: str,
        checked_at: datetime,
        reason: FailureReason,
        terminal_diagnosis: TerminalBrowserDiagnosis | None = None,
    ) -> CheckResult:
        return cls(
            check_id=str(uuid.uuid4()),
            booking_id=booking_id,
            checked_at=checked_at,
            outcome=CheckOutcome.FAILURE,
            extraction_method=ExtractionMethod.NONE,
            failure_reason=reason,
            terminal_diagnosis=terminal_diagnosis,
        )
