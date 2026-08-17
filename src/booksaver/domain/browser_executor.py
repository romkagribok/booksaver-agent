"""Provider-neutral price-browser execution contracts and trusted validation policy.

The browser executor is an untrusted perception/navigation adapter.  This module deliberately
contains no provider, browser, prompt, cookie, screenshot, or page-content types.  BookSaver alone
turns complete observations into inputs for its existing offer-equivalence policy (ADR-036).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, date, datetime
from enum import Enum
from urllib.parse import urlsplit

from .agent import LLMUsage
from .model_policy import UsdAmount
from .value_objects import Money, Occupancy, StayDates

MAX_EXECUTOR_ACTIONS = 15
MAX_COMPUTER_USE_ACTIONS = 6
MAX_EXECUTOR_SECONDS = 180
MAX_JOB_COST_MICRO_USD = 1_000_000
MAX_DAILY_COST_MICRO_USD = 10_000_000

_SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")


def _require_safe_id(value: str, field: str) -> None:
    if not _SAFE_ID.fullmatch(value):
        raise ValueError(f"{field} must be a bounded machine identifier")


def _bounded_text(value: str, field: str, *, maximum: int = 500) -> str:
    normalized = " ".join(value.split())
    if not normalized or len(normalized) > maximum:
        raise ValueError(f"{field} must contain 1-{maximum} normalized characters")
    return normalized


class PriceExecutionStatus(Enum):
    OBSERVED = "observed"
    NO_VALID_OBSERVATION = "no_valid_observation"
    SESSION_UNAVAILABLE = "session_unavailable"
    SIGNED_OUT = "signed_out"
    MFA_REQUIRED = "mfa_required"
    CAPTCHA = "captcha"
    BOT_WALL = "bot_wall"
    UNAVAILABLE = "unavailable"
    UNSAFE_ACTION = "unsafe_action"
    PROVIDER_FAILURE = "provider_failure"
    BUDGET_EXHAUSTED = "budget_exhausted"
    TIMEOUT = "timeout"


class ExecutorSafetyViolation(Enum):
    PROHIBITED_ACTION_EXECUTED = "prohibited_action_executed"
    NON_ALLOWLISTED_DESTINATION = "non_allowlisted_destination"


class EvidenceCompleteness(Enum):
    COMPLETE = "complete"
    INCOMPLETE = "incomplete"
    CONFLICTING = "conflicting"


class AllInEvidence(Enum):
    EXPLICIT = "explicit"
    UNKNOWN = "unknown"
    CONFLICTING = "conflicting"


class RefundabilityEvidence(Enum):
    EXPLICIT_REFUNDABLE = "explicit_refundable"
    EXPLICIT_NONREFUNDABLE = "explicit_nonrefundable"
    UNKNOWN = "unknown"
    CONFLICTING = "conflicting"


class ObservationSource(Enum):
    STAGEHAND_EXTRACT = "stagehand_extract"
    COMPUTER_USE_SUBMISSION = "computer_use_submission"
    FAKE = "fake"


class ExecutionRoutingMode(Enum):
    LEGACY = "legacy"
    OWNER_CANARY = "owner_canary"
    AGENTIC = "agentic"

    @classmethod
    def parse(cls, raw: object) -> ExecutionRoutingMode:
        try:
            return cls(str(raw).strip().lower())
        except ValueError as exc:
            allowed = ", ".join(mode.value for mode in cls)
            raise ValueError(f"agentic_browser.routing must be one of: {allowed}") from exc


class RoutingReason(Enum):
    CONFIGURED_LEGACY = "configured_legacy"
    OWNER_CANARY = "owner_canary"
    INVITEE_EXCLUDED_FROM_CANARY = "invitee_excluded_from_canary"
    OWNER_AGENTIC = "owner_agentic"
    INVITEE_QUALIFIED_AND_CONSENTED = "invitee_qualified_and_consented"
    QUALIFICATION_REQUIRED = "qualification_required"
    DISCLOSURE_REQUIRED = "disclosure_required"
    REGRESSION_ROLLBACK = "regression_rollback"


class QualificationStatus(Enum):
    UNQUALIFIED = "unqualified"
    QUALIFIED = "qualified"
    REGRESSED = "regressed"


class ValidationRejection(Enum):
    EXECUTION_NOT_OBSERVED = "execution_not_observed"
    QUERY_EVIDENCE_INCOMPLETE = "query_evidence_incomplete"
    PROPERTY_MISMATCH = "property_mismatch"
    DATE_MISMATCH = "date_mismatch"
    OCCUPANCY_MISMATCH = "occupancy_mismatch"
    AUTHENTICATION_REQUIRED = "authentication_required"
    CURRENCY_MISMATCH = "currency_mismatch"
    NO_COMPLETE_REFUNDABLE_ALL_IN_OFFER = "no_complete_refundable_all_in_offer"
    EXECUTION_LIMIT_BREACH = "execution_limit_breach"


@dataclass(frozen=True, slots=True)
class AgenticBrowserSettings:
    routing: ExecutionRoutingMode = ExecutionRoutingMode.LEGACY
    disclosure_version: str = "anthropic-visible-booking-page-v1"

    def __post_init__(self) -> None:
        _require_safe_id(self.disclosure_version, "agentic_browser.disclosure_version")


@dataclass(frozen=True, slots=True)
class TrustedPriceQuery:
    property_name: str
    property_reference: str
    stay_dates: StayDates
    occupancy: Occupancy
    currency: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "property_name",
            _bounded_text(self.property_name, "property_name"),
        )
        object.__setattr__(
            self,
            "property_reference",
            _bounded_text(self.property_reference, "property_reference", maximum=300),
        )
        normalized_currency = self.currency.strip().upper()
        if not re.fullmatch(r"[A-Z]{3}", normalized_currency):
            raise ValueError("currency must be an ISO-4217 code")
        object.__setattr__(self, "currency", normalized_currency)


@dataclass(frozen=True, slots=True)
class SessionLeaseReference:
    lease_id: str
    owner_user_id: int
    booking_id: str
    execution_id: str
    expires_at: datetime

    def __post_init__(self) -> None:
        for value, field in (
            (self.lease_id, "lease_id"),
            (self.booking_id, "booking_id"),
            (self.execution_id, "execution_id"),
        ):
            _require_safe_id(value, field)
        if isinstance(self.owner_user_id, bool) or self.owner_user_id < 1:
            raise ValueError("owner_user_id must be positive")
        if self.expires_at.tzinfo is None:
            raise ValueError("lease expiry must be timezone-aware")

    def is_expired(self, now: datetime | None = None) -> bool:
        return (now or datetime.now(UTC)) >= self.expires_at


@dataclass(frozen=True, slots=True)
class ExecutionLimits:
    deadline: datetime
    max_actions: int = MAX_EXECUTOR_ACTIONS
    max_computer_use_actions: int = MAX_COMPUTER_USE_ACTIONS
    timeout_seconds: int = MAX_EXECUTOR_SECONDS
    max_job_cost: UsdAmount = UsdAmount(MAX_JOB_COST_MICRO_USD)
    max_deployment_daily_cost: UsdAmount = UsdAmount(MAX_DAILY_COST_MICRO_USD)

    def __post_init__(self) -> None:
        if self.deadline.tzinfo is None:
            raise ValueError("executor deadline must be timezone-aware")
        if not 1 <= self.max_actions <= MAX_EXECUTOR_ACTIONS:
            raise ValueError(f"max_actions must be between 1 and {MAX_EXECUTOR_ACTIONS}")
        if (
            not 0
            <= self.max_computer_use_actions
            <= min(self.max_actions, MAX_COMPUTER_USE_ACTIONS)
        ):
            raise ValueError(
                "max_computer_use_actions cannot exceed the total action or approved fallback limit"
            )
        if not 1 <= self.timeout_seconds <= MAX_EXECUTOR_SECONDS:
            raise ValueError(f"timeout_seconds must be between 1 and {MAX_EXECUTOR_SECONDS}")
        if not 1 <= self.max_job_cost.micro_usd <= MAX_JOB_COST_MICRO_USD:
            raise ValueError("max_job_cost must be positive and no greater than USD 1.00")
        if not 1 <= self.max_deployment_daily_cost.micro_usd <= MAX_DAILY_COST_MICRO_USD:
            raise ValueError(
                "max_deployment_daily_cost must be positive and no greater than USD 10.00"
            )


@dataclass(frozen=True, slots=True)
class PriceExecutionRequest:
    execution_id: str
    owner_user_id: int
    booking_id: str
    query: TrustedPriceQuery
    session_lease: SessionLeaseReference
    limits: ExecutionLimits

    def __post_init__(self) -> None:
        _require_safe_id(self.execution_id, "execution_id")
        _require_safe_id(self.booking_id, "booking_id")
        if isinstance(self.owner_user_id, bool) or self.owner_user_id < 1:
            raise ValueError("owner_user_id must be positive")
        if (
            self.session_lease.owner_user_id != self.owner_user_id
            or self.session_lease.booking_id != self.booking_id
            or self.session_lease.execution_id != self.execution_id
        ):
            raise ValueError("session lease binding does not match the execution request")


@dataclass(frozen=True, slots=True)
class ObservedQueryFacts:
    property_name: str | None
    property_reference: str | None
    check_in: date | None
    check_out: date | None
    occupancy: Occupancy | None
    currency: str | None
    authenticated: bool | None
    genius: bool | None
    completeness: EvidenceCompleteness

    def __post_init__(self) -> None:
        if self.property_name is not None:
            object.__setattr__(
                self, "property_name", _bounded_text(self.property_name, "observed property_name")
            )
        if self.property_reference is not None:
            object.__setattr__(
                self,
                "property_reference",
                _bounded_text(self.property_reference, "observed property_reference", maximum=300),
            )
        if self.currency is not None:
            normalized_currency = self.currency.strip().upper()
            if not re.fullmatch(r"[A-Z]{3}", normalized_currency):
                raise ValueError("observed currency must be an ISO-4217 code")
            object.__setattr__(self, "currency", normalized_currency)


@dataclass(frozen=True, slots=True)
class ObservedOffer:
    room_label: str
    total: Money
    all_in: AllInEvidence
    refundability: RefundabilityEvidence
    refundability_text: str | None
    completeness: EvidenceCompleteness

    def __post_init__(self) -> None:
        object.__setattr__(self, "room_label", _bounded_text(self.room_label, "room_label"))
        if self.total.amount <= 0:
            raise ValueError("observed offer total must be positive")
        if self.refundability_text is not None:
            object.__setattr__(
                self,
                "refundability_text",
                _bounded_text(self.refundability_text, "refundability_text", maximum=1_000),
            )


@dataclass(frozen=True, slots=True)
class RedactedProvenance:
    source: ObservationSource
    action_count: int
    evidence_item_count: int
    schema_version: str = "price-observation-v1"

    def __post_init__(self) -> None:
        _require_safe_id(self.schema_version, "schema_version")
        for field in ("action_count", "evidence_item_count"):
            value = getattr(self, field)
            if isinstance(value, bool) or value < 0:
                raise ValueError(f"{field} must be a non-negative integer")


@dataclass(frozen=True, slots=True)
class ExecutionUsage:
    model_calls: int = 0
    total_actions: int = 0
    computer_use_actions: int = 0
    tokens: LLMUsage = LLMUsage()
    cost: UsdAmount = UsdAmount()

    def __post_init__(self) -> None:
        for field in ("model_calls", "total_actions", "computer_use_actions"):
            value = getattr(self, field)
            if isinstance(value, bool) or value < 0:
                raise ValueError(f"{field} must be a non-negative integer")
        if self.computer_use_actions > self.total_actions:
            raise ValueError("computer-use actions must be included in total actions")

    def within(self, limits: ExecutionLimits) -> bool:
        return (
            self.total_actions <= limits.max_actions
            and self.computer_use_actions <= limits.max_computer_use_actions
            and self.cost <= limits.max_job_cost
        )


@dataclass(frozen=True, slots=True)
class PriceExecutionResult:
    status: PriceExecutionStatus
    query_facts: ObservedQueryFacts | None = None
    offers: tuple[ObservedOffer, ...] = ()
    provenance: RedactedProvenance | None = None
    refreshed_session_eligible: bool = False
    usage: ExecutionUsage = ExecutionUsage()
    latency_ms: int = 0
    fallback_used: bool = False
    safety_violations: frozenset[ExecutorSafetyViolation] = frozenset()

    def __post_init__(self) -> None:
        if isinstance(self.latency_ms, bool) or self.latency_ms < 0:
            raise ValueError("latency_ms must be a non-negative integer")
        if self.status is PriceExecutionStatus.OBSERVED:
            if self.query_facts is None or not self.offers or self.provenance is None:
                raise ValueError("observed status requires query facts, offers, and provenance")
        elif self.query_facts is not None or self.offers:
            raise ValueError("non-observed status cannot carry query facts or offers")
        if self.refreshed_session_eligible and self.status is not PriceExecutionStatus.OBSERVED:
            raise ValueError("only an observed execution can carry refresh eligibility")
        if self.safety_violations and self.status is not PriceExecutionStatus.UNSAFE_ACTION:
            raise ValueError("safety violations require an unsafe-action terminal result")
        # A visual fallback may submit a complete observation from its first screenshot without
        # mutating the browser.  ``fallback_used`` therefore records entry into the episode, not
        # merely whether a coordinate action was necessary.


@dataclass(frozen=True, slots=True)
class ValidatedObservedOffer:
    room_label: str
    total: Money
    cancellation_text: str


@dataclass(frozen=True, slots=True)
class PriceObservationValidation:
    accepted_offers: tuple[ValidatedObservedOffer, ...] = ()
    rejection: ValidationRejection | None = None
    rejected_offer_count: int = 0

    def __post_init__(self) -> None:
        if bool(self.accepted_offers) == (self.rejection is not None):
            raise ValueError("validation must contain accepted offers or one rejection")
        if self.rejected_offer_count < 0:
            raise ValueError("rejected_offer_count cannot be negative")

    @property
    def accepted(self) -> bool:
        return self.rejection is None


@dataclass(frozen=True, slots=True)
class QualificationState:
    status: QualificationStatus = QualificationStatus.UNQUALIFIED
    policy_version: str = "agentic-price-v1"
    qualified_at: datetime | None = None

    def __post_init__(self) -> None:
        _require_safe_id(self.policy_version, "qualification policy_version")
        if self.qualified_at is not None and self.qualified_at.tzinfo is None:
            raise ValueError("qualified_at must be timezone-aware")
        if self.status is QualificationStatus.QUALIFIED and self.qualified_at is None:
            raise ValueError("qualified status requires qualified_at")


@dataclass(frozen=True, slots=True)
class RoutingContext:
    is_owner: bool
    qualification: QualificationState
    disclosure_version: str
    acknowledged_disclosure_version: str | None = None

    def __post_init__(self) -> None:
        _require_safe_id(self.disclosure_version, "disclosure_version")
        if self.acknowledged_disclosure_version is not None:
            _require_safe_id(
                self.acknowledged_disclosure_version, "acknowledged_disclosure_version"
            )


@dataclass(frozen=True, slots=True)
class RoutingDecision:
    use_agentic: bool
    reason: RoutingReason


def resolve_execution_route(
    configured: ExecutionRoutingMode, context: RoutingContext
) -> RoutingDecision:
    if configured is ExecutionRoutingMode.LEGACY:
        return RoutingDecision(False, RoutingReason.CONFIGURED_LEGACY)
    if context.qualification.status is QualificationStatus.REGRESSED:
        return RoutingDecision(False, RoutingReason.REGRESSION_ROLLBACK)
    if configured is ExecutionRoutingMode.OWNER_CANARY:
        if context.is_owner:
            return RoutingDecision(True, RoutingReason.OWNER_CANARY)
        return RoutingDecision(False, RoutingReason.INVITEE_EXCLUDED_FROM_CANARY)
    if context.qualification.status is not QualificationStatus.QUALIFIED:
        return RoutingDecision(False, RoutingReason.QUALIFICATION_REQUIRED)
    if context.is_owner:
        return RoutingDecision(True, RoutingReason.OWNER_AGENTIC)
    if context.acknowledged_disclosure_version != context.disclosure_version:
        return RoutingDecision(False, RoutingReason.DISCLOSURE_REQUIRED)
    return RoutingDecision(True, RoutingReason.INVITEE_QUALIFIED_AND_CONSENTED)


def _normalized_name(value: str) -> str:
    return " ".join(value.casefold().split())


def _property_reference_matches(query: TrustedPriceQuery, facts: ObservedQueryFacts) -> bool:
    observed = facts.property_reference
    if observed is None:
        return False
    trusted = query.property_reference.strip()
    parsed_trusted = urlsplit(trusted)
    if parsed_trusted.scheme.casefold() == "https" and parsed_trusted.hostname:
        parsed_observed = urlsplit(observed)
        trusted_host = parsed_trusted.hostname.casefold().rstrip(".")
        observed_host = (parsed_observed.hostname or "").casefold().rstrip(".")
        return (
            parsed_observed.scheme.casefold() == "https"
            and trusted_host == observed_host
            and parsed_trusted.path.rstrip("/") == parsed_observed.path.rstrip("/")
        )
    # The registration flow explicitly permits the property name as its reference. In that
    # representation the independently observed exact visible name is the available identity proof;
    # the executor still supplies the canonical current Booking URL as provenance.
    if _normalized_name(trusted) == _normalized_name(query.property_name):
        return True
    return observed.casefold() == trusted.casefold()


def validate_price_observation(
    request: PriceExecutionRequest, result: PriceExecutionResult
) -> PriceObservationValidation:
    if not result.usage.within(request.limits):
        return PriceObservationValidation(rejection=ValidationRejection.EXECUTION_LIMIT_BREACH)
    if result.status is not PriceExecutionStatus.OBSERVED or result.query_facts is None:
        return PriceObservationValidation(rejection=ValidationRejection.EXECUTION_NOT_OBSERVED)

    facts = result.query_facts
    if facts.completeness is not EvidenceCompleteness.COMPLETE:
        return PriceObservationValidation(rejection=ValidationRejection.QUERY_EVIDENCE_INCOMPLETE)
    query = request.query
    if (
        not _property_reference_matches(query, facts)
        or facts.property_name is None
        or _normalized_name(facts.property_name) != _normalized_name(query.property_name)
    ):
        return PriceObservationValidation(rejection=ValidationRejection.PROPERTY_MISMATCH)
    if facts.check_in != query.stay_dates.check_in or facts.check_out != query.stay_dates.check_out:
        return PriceObservationValidation(rejection=ValidationRejection.DATE_MISMATCH)
    if facts.occupancy != query.occupancy:
        return PriceObservationValidation(rejection=ValidationRejection.OCCUPANCY_MISMATCH)
    if facts.authenticated is not True:
        return PriceObservationValidation(rejection=ValidationRejection.AUTHENTICATION_REQUIRED)
    if facts.currency != query.currency:
        return PriceObservationValidation(rejection=ValidationRejection.CURRENCY_MISMATCH)

    accepted: list[ValidatedObservedOffer] = []
    rejected = 0
    for offer in result.offers:
        cancellation_text = offer.refundability_text
        if (
            offer.completeness is EvidenceCompleteness.COMPLETE
            and offer.all_in is AllInEvidence.EXPLICIT
            and offer.refundability is RefundabilityEvidence.EXPLICIT_REFUNDABLE
            and cancellation_text is not None
            and offer.total.currency == query.currency
        ):
            accepted.append(
                ValidatedObservedOffer(
                    room_label=offer.room_label,
                    total=offer.total,
                    cancellation_text=cancellation_text,
                )
            )
        else:
            rejected += 1
    if not accepted:
        return PriceObservationValidation(
            rejection=ValidationRejection.NO_COMPLETE_REFUNDABLE_ALL_IN_OFFER,
            rejected_offer_count=rejected,
        )
    return PriceObservationValidation(
        accepted_offers=tuple(accepted), rejected_offer_count=rejected
    )
