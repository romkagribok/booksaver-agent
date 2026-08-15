"""Provider-neutral domain types for resilient Booking.com browser steps.

The types in this module intentionally contain no selectors, raw page content,
URLs, scripts, Playwright objects, or provider response payloads.  They are the
closed vocabulary shared by browser adapters, application policy, and workflow
outcome mapping when Booking.com's DOM changes.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from .model_policy import ModelStopReason

_SAFE_CODE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_VISIBLE_URL_OR_QUERY = re.compile(
    r"(?:https?://|www\.|(?:^|[?&])[A-Za-z0-9_.~-]+=[^\s&]+)",
    re.IGNORECASE,
)
_SECRET_MATERIAL = re.compile(
    r"(?:cookie\s*:|authorization\s*:|bearer\s+[A-Za-z0-9._~-]{8,}|"
    r"(?:password|passwd|secret|api[_ -]?key)\s*[:=])",
    re.IGNORECASE,
)
_AUTHORITATIVE_CLAIM = re.compile(
    r"\b(?:no\s+(?:reservations?|bookings?|rooms?|offers?|results?)|"
    r"(?:inventory|pagination|traversal)\s+(?:is\s+)?complete|"
    r"all\s+(?:pages?|results?|reservations?)\s+(?:were\s+)?(?:read|seen|checked)|"
    r"(?:is\s+)?(?:equivalent|eligible|safe|accepted)|"
    r"(?:reservation|booking)\s+(?:was\s+)?(?:cancelled|canceled|modified))\b",
    re.IGNORECASE,
)
_MAX_VISIBLE_CONTENT_LENGTH = 512


class DomJourney(Enum):
    REMOTE_AUTH = "remote_auth"
    SESSION_VALIDATION = "session_validation"
    ACCOUNT_INVENTORY = "account_inventory"
    PRICE_SEARCH = "price_search"


class DomStepId(Enum):
    REMOTE_AUTH_SESSION_CAPTURE = "remote_auth.session_capture"
    SESSION_VALIDATION = "session.validation"
    INVENTORY_ENTRY = "inventory.entry"
    INVENTORY_READINESS = "inventory.readiness"
    INVENTORY_SCOPE = "inventory.scope"
    INVENTORY_PAGINATION = "inventory.pagination"
    INVENTORY_DETAIL = "inventory.detail"
    INVENTORY_EXTRACTION = "inventory.extraction"
    INVENTORY_COMPLETENESS = "inventory.completeness"
    PRICE_SEARCH_QUERY_SUBMISSION = "price_search.query_submission"
    PRICE_SEARCH_RESULTS = "price_search.results"
    PRICE_CONSENT_OVERLAY = "price_search.consent_overlay"
    PRICE_PROPERTY_LOCATE = "price_search.property_locate"
    PRICE_PROPERTY_OPEN = "price_search.property_open"
    PRICE_CONTEXT_VERIFY = "price_search.context_verify"
    PRICE_ROOM_RATE_READINESS = "price_search.room_rate_readiness"
    PRICE_CURRENCY_ALIGN = "price_search.currency_align"
    PRICE_SNAPSHOT = "price_search.snapshot"
    PRICE_OFFER_EXTRACTION = "price_search.offer_extraction"


class PageState(Enum):
    OBSERVATION_UNAVAILABLE = "observation_unavailable"
    AUTHENTICATION_REQUIRED = "authentication_required"
    MFA_REQUIRED = "mfa_required"
    CAPTCHA = "captcha"
    BOT_WALL = "bot_wall"
    EXTERNAL = "external"
    PROHIBITED = "prohibited"
    AUTHENTICATED_CANDIDATE = "authenticated_candidate"
    VERIFIED_AUTHENTICATED = "verified_authenticated"
    INVENTORY = "inventory"
    SEARCH_RESULTS = "search_results"
    PROPERTY = "property"
    UNSUPPORTED = "unsupported"
    AMBIGUOUS = "ambiguous"

    @property
    def is_protected(self) -> bool:
        return self in PROTECTED_PAGE_STATES


class PageStateSource(Enum):
    DETERMINISTIC = "deterministic"
    SONNET = "sonnet"
    OPUS = "opus"


class EvidenceCategory(Enum):
    OBSERVATION_UNAVAILABLE = "observation_unavailable"
    EXTERNAL_DESTINATION = "external_destination"
    PROHIBITED_OR_MUTATING_DESTINATION = "prohibited_or_mutating_destination"
    CAPTCHA_CHALLENGE = "captcha_challenge"
    BOT_WALL = "bot_wall"
    MFA_CONTROL = "mfa_control"
    CREDENTIAL_CONTROL = "credential_control"
    WEAK_ACCOUNT_CHROME = "weak_account_chrome"
    SUPPORTED_ACCOUNT_STRUCTURE = "supported_account_structure"
    SUPPORTED_INVENTORY_STRUCTURE = "supported_inventory_structure"
    SUPPORTED_SEARCH_RESULTS_STRUCTURE = "supported_search_results_structure"
    SUPPORTED_PROPERTY_STRUCTURE = "supported_property_structure"
    UNSUPPORTED_PAGE_STRUCTURE = "unsupported_page_structure"


class DomCapability(Enum):
    INSPECT_VISIBLE_STRUCTURE = "inspect_visible_structure"
    NAVIGATE_APPROVED_READ_ONLY = "navigate_approved_read_only"
    ACTIVATE_READ_ONLY_CONTROL = "activate_read_only_control"
    DISMISS_CONSENT = "dismiss_consent"
    ADOPT_APPROVED_READ_ONLY_POPUP = "adopt_approved_read_only_popup"
    INTERPRET_VISIBLE_FACTS = "interpret_visible_facts"


class OperatorAction(Enum):
    NONE = "none"
    CONNECT = "connect"
    COMPLETE_MFA = "complete_mfa"
    RETRY_LATER = "retry_later"
    MAINTAIN_CODE = "maintain_code"


class AdaptiveRecoveryPolicy(Enum):
    NONE = "none"
    DIAGNOSIS_ONLY = "diagnosis_only"
    GUARDED_READ_ONLY = "guarded_read_only"


class SemanticSchema(Enum):
    NONE = "none"
    PAGE_STATE = "page_state"
    INVENTORY_STRUCTURE = "inventory_structure"
    INVENTORY_RESERVATIONS = "inventory_reservations"
    SEARCH_STRUCTURE = "search_structure"
    PROPERTY_CONTEXT = "property_context"
    ROOM_RATE_STRUCTURE = "room_rate_structure"
    CURRENCY_STATE = "currency_state"
    OFFER_FACTS = "offer_facts"


class SemanticFactKey(Enum):
    """Positive visible facts that a model may report but never verify."""

    PROPERTY_IDENTITY = "property_identity"
    STAY_DATES = "stay_dates"
    OCCUPANCY = "occupancy"
    CURRENCY = "currency"
    ROOM_RATE_CONTENT = "room_rate_content"
    INVENTORY_SCOPE = "inventory_scope"
    PAGINATION_PROGRESS = "pagination_progress"
    RESERVATION_IDENTITY = "reservation_identity"
    REFUNDABILITY_EVIDENCE = "refundability_evidence"


class VisibleEvidenceKind(Enum):
    ELEMENT_REFERENCE = "element_reference"
    VISIBLE_EXCERPT = "visible_excerpt"


class StepVerificationStatus(Enum):
    VERIFIED = "verified"
    AMBIGUOUS = "ambiguous"
    EXACT_FAILURE = "exact_failure"


class DiagnosisProvenance(Enum):
    DETERMINISTIC = "deterministic"
    CODE_VERIFIER_DIAGNOSED = "code_verifier_diagnosed"
    SONNET_RECOVERED = "sonnet_recovered"
    OPUS_RECOVERED = "opus_recovered"
    SONNET_DIAGNOSED = "sonnet_diagnosed"
    OPUS_DIAGNOSED = "opus_diagnosed"
    POLICY_STOP = "policy_stop"
    PROVIDER_STOP = "provider_stop"
    BUDGET_STOP = "budget_stop"
    INFRASTRUCTURE_STOP = "infrastructure_stop"


class PopupRefusalReason(Enum):
    NONE_OPENED = "none_opened"
    MULTIPLE_OPENED = "multiple_opened"
    EXTERNAL_ORIGIN = "external_origin"
    PROTECTED_DESTINATION = "protected_destination"
    MUTATING_DESTINATION = "mutating_destination"
    IRRELEVANT_TO_STEP = "irrelevant_to_step"
    UNSUPPORTED_ROUTE = "unsupported_route"
    OBSERVATION_UNAVAILABLE = "observation_unavailable"


class TerminalBrowserReason(Enum):
    POSTCONDITION_SATISFIED = "postcondition_satisfied"
    CODE_VERIFICATION_REQUIRED = "code_verification_required"
    AUTHENTICATION_REQUIRED = "authentication_required"
    MFA_REQUIRED = "mfa_required"
    BOT_WALL = "bot_wall"
    BLOCKED_DESTINATION = "blocked_destination"
    PROHIBITED_ACTION = "prohibited_action"
    UNSUPPORTED_PAGE = "unsupported_page"
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
    EXPLICIT_UNAVAILABLE = "explicit_unavailable"
    PROPERTY_CONTEXT_MISMATCH = "property_context_mismatch"
    CURRENCY_MISMATCH = "currency_mismatch"
    CANDIDATES_REJECTED = "candidates_rejected"
    POPUP_REFUSED = "popup_refused"
    INFRASTRUCTURE_FAILURE = "infrastructure_failure"
    CODE_MAINTENANCE_REQUIRED = "code_maintenance_required"
    DETERMINISTIC_REJECTION = "deterministic_rejection"
    UNRESOLVED_AMBIGUITY = "unresolved_ambiguity"
    COST_ACCOUNTING_ERROR = "cost_accounting_error"
    CLOCK_ROLLBACK = "clock_rollback"


PROTECTED_PAGE_STATES = frozenset(
    {
        PageState.OBSERVATION_UNAVAILABLE,
        PageState.AUTHENTICATION_REQUIRED,
        PageState.MFA_REQUIRED,
        PageState.CAPTCHA,
        PageState.BOT_WALL,
        PageState.EXTERNAL,
        PageState.PROHIBITED,
    }
)

CODE_VERIFIABLE_PAGE_STATES = frozenset(
    {
        PageState.VERIFIED_AUTHENTICATED,
        PageState.INVENTORY,
        PageState.SEARCH_RESULTS,
        PageState.PROPERTY,
    }
)


@dataclass(frozen=True, slots=True)
class EvidenceReference:
    """A content-free reference to one bounded observation signal."""

    category: EvidenceCategory
    reference: str

    def __post_init__(self) -> None:
        if not _SAFE_CODE.fullmatch(self.reference):
            raise ValueError("evidence reference must be a bounded machine code")


@dataclass(frozen=True, slots=True)
class FreshPageObservation:
    """Allowlisted structural evidence captured from one fresh browser state."""

    observation_id: str
    observed_at: datetime
    evidence: frozenset[EvidenceCategory]
    evidence_references: tuple[EvidenceReference, ...] = ()

    def __post_init__(self) -> None:
        if not _SAFE_CODE.fullmatch(self.observation_id):
            raise ValueError("observation_id must be a bounded machine code")
        if self.observed_at.tzinfo is None:
            raise ValueError("observed_at must be timezone-aware")
        if any(ref.category not in self.evidence for ref in self.evidence_references):
            raise ValueError("evidence references must name an observed category")
        if len({(ref.category, ref.reference) for ref in self.evidence_references}) != len(
            self.evidence_references
        ):
            raise ValueError("evidence references must be unique")


@dataclass(frozen=True, slots=True)
class PageStateClassification:
    state: PageState
    confidence: float
    evidence: frozenset[EvidenceCategory]
    evidence_references: tuple[EvidenceReference, ...]
    operator_action: OperatorAction
    source: PageStateSource
    observation_id: str

    def __post_init__(self) -> None:
        if isinstance(self.confidence, bool) or not 0.0 <= self.confidence <= 1.0:
            raise ValueError("classification confidence must be between zero and one")
        if not _SAFE_CODE.fullmatch(self.observation_id):
            raise ValueError("observation_id must be a bounded machine code")
        if any(ref.category not in self.evidence for ref in self.evidence_references):
            raise ValueError("classification references must name classification evidence")
        if self.source is not PageStateSource.DETERMINISTIC and (
            self.state is PageState.VERIFIED_AUTHENTICATED
        ):
            raise ValueError("a model cannot verify authentication")
        expected_action = operator_action_for(self.state)
        if self.operator_action is not expected_action:
            raise ValueError(f"{self.state.value} requires operator action {expected_action.value}")


@dataclass(frozen=True, slots=True)
class CodeVerificationReceipt:
    """Code-owned proof that a named postcondition held on a fresh observation."""

    step_id: DomStepId
    verified_state: PageState
    observation_id: str
    verified_at: datetime
    verifier: str

    def __post_init__(self) -> None:
        if self.verified_state not in CODE_VERIFIABLE_PAGE_STATES:
            raise ValueError("only a supported page state can receive a code receipt")
        if not _SAFE_CODE.fullmatch(self.observation_id):
            raise ValueError("observation_id must be a bounded machine code")
        if self.verified_at.tzinfo is None:
            raise ValueError("verified_at must be timezone-aware")
        if not _SAFE_CODE.fullmatch(self.verifier):
            raise ValueError("verifier must be a bounded machine code")


def _validate_visible_content(value: str, *, field_name: str) -> None:
    if not value or value != value.strip():
        raise ValueError(f"{field_name} must be non-empty and normalized")
    if len(value) > _MAX_VISIBLE_CONTENT_LENGTH:
        raise ValueError(f"{field_name} exceeds the visible-content limit")
    if any(ord(character) < 32 for character in value):
        raise ValueError(f"{field_name} cannot contain control characters")
    if _VISIBLE_URL_OR_QUERY.search(value):
        raise ValueError(f"{field_name} cannot contain a URL or query value")
    if _SECRET_MATERIAL.search(value):
        raise ValueError(f"{field_name} cannot contain secret material")


@dataclass(frozen=True, slots=True)
class VisibleEvidence:
    """One bounded, current, visible grounding item; never hidden browser state."""

    evidence_id: str
    kind: VisibleEvidenceKind
    content: str

    def __post_init__(self) -> None:
        if not _SAFE_CODE.fullmatch(self.evidence_id):
            raise ValueError("evidence_id must be a bounded machine code")
        if not isinstance(self.kind, VisibleEvidenceKind):
            raise ValueError("visible evidence kind must use the closed vocabulary")
        if self.kind is VisibleEvidenceKind.ELEMENT_REFERENCE:
            if not _SAFE_CODE.fullmatch(self.content):
                raise ValueError("element evidence must be a fresh bounded reference")
            return
        _validate_visible_content(self.content, field_name="visible excerpt")


@dataclass(frozen=True, slots=True)
class SemanticFact:
    """An advisory positive fact whose authority remains with a code verifier."""

    fact_id: str
    key: SemanticFactKey
    value: str
    evidence_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if not _SAFE_CODE.fullmatch(self.fact_id):
            raise ValueError("fact_id must be a bounded machine code")
        if not isinstance(self.key, SemanticFactKey):
            raise ValueError("semantic fact key must use the closed positive vocabulary")
        _validate_visible_content(self.value, field_name="semantic fact value")
        if _AUTHORITATIVE_CLAIM.search(self.value):
            raise ValueError("semantic facts cannot make authoritative domain claims")
        if not self.evidence_ids:
            raise ValueError("every semantic fact requires visible grounding")
        if len(set(self.evidence_ids)) != len(self.evidence_ids):
            raise ValueError("semantic fact evidence references must be unique")
        if any(not _SAFE_CODE.fullmatch(item) for item in self.evidence_ids):
            raise ValueError("semantic fact evidence must use bounded identifiers")


@dataclass(frozen=True, slots=True)
class SemanticStepObservation:
    """Positive-only model output tied to one fresh registered page observation.

    The closed fact-key vocabulary intentionally has no key for absence,
    completeness, equivalence, eligibility, accepted price, lifecycle mutation,
    or action safety.  Consumers must compare every value with trusted inputs.
    """

    step_id: DomStepId
    observation_id: str
    facts: tuple[SemanticFact, ...]
    visible_evidence: tuple[VisibleEvidence, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.step_id, DomStepId):
            raise ValueError("semantic observation requires a registered step")
        if not _SAFE_CODE.fullmatch(self.observation_id):
            raise ValueError("observation_id must be a bounded machine code")
        if not self.facts:
            raise ValueError("a semantic observation must contain a positive fact")
        fact_ids = tuple(fact.fact_id for fact in self.facts)
        if len(set(fact_ids)) != len(fact_ids):
            raise ValueError("semantic fact identifiers must be unique")
        evidence_ids = tuple(item.evidence_id for item in self.visible_evidence)
        if len(set(evidence_ids)) != len(evidence_ids):
            raise ValueError("visible evidence identifiers must be unique")
        evidence_set = set(evidence_ids)
        if any(
            evidence_id not in evidence_set
            for fact in self.facts
            for evidence_id in fact.evidence_ids
        ):
            raise ValueError("every semantic fact must reference current visible evidence")


@dataclass(frozen=True, slots=True)
class StepVerificationResult:
    """Code-owned three-state decision for one semantic postcondition."""

    step_id: DomStepId
    observation_id: str
    status: StepVerificationStatus
    evidence: frozenset[EvidenceCategory]
    receipt: CodeVerificationReceipt | None = None
    exact_reason: TerminalBrowserReason | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.step_id, DomStepId):
            raise ValueError("verification requires a registered step")
        if not isinstance(self.status, StepVerificationStatus):
            raise ValueError("verification status must use the closed vocabulary")
        if any(not isinstance(item, EvidenceCategory) for item in self.evidence):
            raise ValueError("verification evidence must use safe categories")
        if not _SAFE_CODE.fullmatch(self.observation_id):
            raise ValueError("observation_id must be a bounded machine code")
        if self.status is StepVerificationStatus.VERIFIED:
            if self.receipt is None or self.exact_reason is not None:
                raise ValueError("verified results require only a code receipt")
            if (
                self.receipt.step_id is not self.step_id
                or self.receipt.observation_id != self.observation_id
            ):
                raise ValueError("verification receipt must prove this fresh step")
            return
        if self.receipt is not None:
            raise ValueError("only verified results may carry a code receipt")
        if self.status is StepVerificationStatus.AMBIGUOUS:
            if self.exact_reason is not None:
                raise ValueError("ambiguous results cannot claim an exact reason")
            return
        if self.exact_reason is None:
            raise ValueError("exact failures require a typed reason")
        if not isinstance(self.exact_reason, TerminalBrowserReason):
            raise ValueError("exact failure reason must use the closed vocabulary")
        if self.exact_reason in {
            TerminalBrowserReason.POSTCONDITION_SATISFIED,
            TerminalBrowserReason.CODE_VERIFICATION_REQUIRED,
            TerminalBrowserReason.UNRESOLVED_AMBIGUITY,
            TerminalBrowserReason.CODE_MAINTENANCE_REQUIRED,
        }:
            raise ValueError("an exact code failure cannot be model ambiguity or success")


@dataclass(frozen=True, slots=True)
class TerminalBrowserDiagnosis:
    """Bounded, content-free final result shared across browser workflows."""

    reason: TerminalBrowserReason
    step_id: DomStepId
    provenance: DiagnosisProvenance
    confidence: float
    evidence: frozenset[EvidenceCategory]
    operator_action: OperatorAction
    code_maintenance_required: bool = False
    model_stop_reason: ModelStopReason | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.reason, TerminalBrowserReason):
            raise ValueError("diagnosis reason must use the closed vocabulary")
        if not isinstance(self.step_id, DomStepId):
            raise ValueError("diagnosis requires a registered step")
        if not isinstance(self.provenance, DiagnosisProvenance):
            raise ValueError("diagnosis provenance must use the closed vocabulary")
        if any(not isinstance(item, EvidenceCategory) for item in self.evidence):
            raise ValueError("diagnosis evidence must use safe categories")
        if not isinstance(self.operator_action, OperatorAction):
            raise ValueError("diagnosis operator action must use the closed vocabulary")
        if self.model_stop_reason is not None and not isinstance(
            self.model_stop_reason, ModelStopReason
        ):
            raise ValueError("diagnosis model stop must use the closed vocabulary")
        if isinstance(self.confidence, bool) or not 0.0 <= self.confidence <= 1.0:
            raise ValueError("diagnosis confidence must be between zero and one")
        if (
            self.provenance
            in {
                DiagnosisProvenance.DETERMINISTIC,
                DiagnosisProvenance.CODE_VERIFIER_DIAGNOSED,
                DiagnosisProvenance.POLICY_STOP,
                DiagnosisProvenance.PROVIDER_STOP,
                DiagnosisProvenance.BUDGET_STOP,
                DiagnosisProvenance.INFRASTRUCTURE_STOP,
            }
            and self.confidence != 1.0
        ):
            raise ValueError("non-model terminal provenance must be conclusive")
        maintenance = self.reason is TerminalBrowserReason.CODE_MAINTENANCE_REQUIRED
        if self.code_maintenance_required is not maintenance:
            raise ValueError("maintenance flag must match the terminal reason")
        if maintenance and self.provenance not in {
            DiagnosisProvenance.CODE_VERIFIER_DIAGNOSED,
            DiagnosisProvenance.SONNET_DIAGNOSED,
            DiagnosisProvenance.OPUS_DIAGNOSED,
        }:
            raise ValueError("only a model diagnosis or code verifier may request code maintenance")
        if (
            self.provenance
            in {
                DiagnosisProvenance.SONNET_RECOVERED,
                DiagnosisProvenance.OPUS_RECOVERED,
            }
            and self.reason is not TerminalBrowserReason.POSTCONDITION_SATISFIED
        ):
            raise ValueError("recovery provenance requires a satisfied postcondition")
        if self.reason is TerminalBrowserReason.POSTCONDITION_SATISFIED and (
            self.provenance
            not in {
                DiagnosisProvenance.DETERMINISTIC,
                DiagnosisProvenance.SONNET_RECOVERED,
                DiagnosisProvenance.OPUS_RECOVERED,
            }
        ):
            raise ValueError("postcondition success requires recovery provenance")
        expected_action = operator_action_for_reason(self.reason)
        if self.operator_action is not expected_action:
            raise ValueError(
                f"{self.reason.value} requires operator action {expected_action.value}"
            )


def validate_assisted_diagnoses(
    diagnoses: tuple[TerminalBrowserDiagnosis, ...],
) -> None:
    """Require ordered, positive, content-free model recovery receipts."""

    if any(
        item.reason is not TerminalBrowserReason.POSTCONDITION_SATISFIED
        or item.provenance
        not in {
            DiagnosisProvenance.SONNET_RECOVERED,
            DiagnosisProvenance.OPUS_RECOVERED,
        }
        or item.code_maintenance_required
        for item in diagnoses
    ):
        raise ValueError("assisted diagnoses must be positive model recovery receipts")


@dataclass(frozen=True, slots=True)
class PopupAdoptionReceipt:
    step_id: DomStepId
    observation_id: str
    page_id: str
    adopted_at: datetime

    def __post_init__(self) -> None:
        if not isinstance(self.step_id, DomStepId):
            raise ValueError("popup adoption requires a registered step")
        if not _SAFE_CODE.fullmatch(self.observation_id):
            raise ValueError("observation_id must be a bounded machine code")
        if not _SAFE_CODE.fullmatch(self.page_id):
            raise ValueError("page_id must be a bounded machine code")
        if self.adopted_at.tzinfo is None:
            raise ValueError("adopted_at must be timezone-aware")


@dataclass(frozen=True, slots=True)
class PopupAdoptionResult:
    receipt: PopupAdoptionReceipt | None = None
    refusal_reason: PopupRefusalReason | None = None

    def __post_init__(self) -> None:
        if self.refusal_reason is not None and not isinstance(
            self.refusal_reason, PopupRefusalReason
        ):
            raise ValueError("popup refusal must use the closed vocabulary")
        if (self.receipt is None) == (self.refusal_reason is None):
            raise ValueError("popup result requires exactly one receipt or refusal")

    @property
    def is_adopted(self) -> bool:
        return self.receipt is not None


@dataclass(frozen=True, slots=True)
class StateTerminalMapping:
    state: PageState
    reason: TerminalBrowserReason


@dataclass(frozen=True, slots=True)
class ModelStopTerminalMapping:
    stop: ModelStopReason
    reason: TerminalBrowserReason


@dataclass(frozen=True, slots=True)
class DomStepDefinition:
    step_id: DomStepId
    journey: DomJourney
    deterministic_postcondition: str
    safe_capabilities: frozenset[DomCapability]
    protected_states: frozenset[PageState]
    supported_states: frozenset[PageState]
    semantic_schema: SemanticSchema
    recovery_policy: AdaptiveRecoveryPolicy
    state_mappings: tuple[StateTerminalMapping, ...]
    model_stop_mappings: tuple[ModelStopTerminalMapping, ...]

    def __post_init__(self) -> None:
        if not _SAFE_CODE.fullmatch(self.deterministic_postcondition):
            raise ValueError("postcondition must be a bounded machine code")
        if not self.protected_states.issuperset(PROTECTED_PAGE_STATES):
            raise ValueError("every DOM step must preserve all protected page states")
        if not self.supported_states or not self.supported_states.issubset(
            CODE_VERIFIABLE_PAGE_STATES
        ):
            raise ValueError("supported states must be non-empty and code-verifiable")
        if self.recovery_policy is not AdaptiveRecoveryPolicy.GUARDED_READ_ONLY and (
            self.safe_capabilities
        ):
            raise ValueError("non-recovery steps cannot expose browser capabilities")
        state_keys = tuple(item.state for item in self.state_mappings)
        if len(set(state_keys)) != len(state_keys) or set(state_keys) != set(PageState):
            raise ValueError("state terminal mappings must be unique and total")
        stop_keys = tuple(item.stop for item in self.model_stop_mappings)
        if len(set(stop_keys)) != len(stop_keys) or set(stop_keys) != set(ModelStopReason):
            raise ValueError("model-stop terminal mappings must be unique and total")

    def reason_for_state(self, state: PageState) -> TerminalBrowserReason:
        return next(item.reason for item in self.state_mappings if item.state is state)

    def reason_for_model_stop(self, stop: ModelStopReason) -> TerminalBrowserReason:
        return next(item.reason for item in self.model_stop_mappings if item.stop is stop)


class DomStepRegistry:
    """Validated aggregate containing exactly one definition per declared step."""

    def __init__(self, definitions: tuple[DomStepDefinition, ...]) -> None:
        identifiers = tuple(definition.step_id for definition in definitions)
        if len(set(identifiers)) != len(identifiers):
            raise ValueError("DOM step identifiers must be unique")
        if set(identifiers) != set(DomStepId):
            missing = sorted(step.value for step in set(DomStepId) - set(identifiers))
            extra = sorted(step.value for step in set(identifiers) - set(DomStepId))
            raise ValueError(f"DOM step coverage mismatch: missing={missing}; extra={extra}")
        self._definitions = definitions
        self._by_id = {definition.step_id: definition for definition in definitions}

    @property
    def definitions(self) -> tuple[DomStepDefinition, ...]:
        return self._definitions

    @property
    def step_ids(self) -> frozenset[DomStepId]:
        return frozenset(self._by_id)

    def definition(self, step_id: DomStepId) -> DomStepDefinition:
        return self._by_id[step_id]


@dataclass(frozen=True, slots=True)
class PageStateResolution:
    classification: PageStateClassification | None
    terminal_reason: TerminalBrowserReason
    verification_receipt: CodeVerificationReceipt | None = None
    model_stop_reason: ModelStopReason | None = None

    def __post_init__(self) -> None:
        if self.verification_receipt is not None:
            if self.classification is None:
                raise ValueError("a verification receipt requires a classification")
            if self.classification.source is not PageStateSource.DETERMINISTIC:
                raise ValueError("model classifications cannot receive verification receipts")
            if self.classification.observation_id != self.verification_receipt.observation_id:
                raise ValueError("verification receipt must use the fresh classification")
            if self.classification.state is not self.verification_receipt.verified_state:
                raise ValueError("verification receipt must prove the classified state")
        if self.model_stop_reason is not None and self.terminal_reason in {
            TerminalBrowserReason.POSTCONDITION_SATISFIED,
            TerminalBrowserReason.CODE_VERIFICATION_REQUIRED,
        }:
            raise ValueError("a successful or candidate state cannot carry a model stop")


def operator_action_for(state: PageState) -> OperatorAction:
    if state is PageState.AUTHENTICATION_REQUIRED:
        return OperatorAction.CONNECT
    if state is PageState.MFA_REQUIRED:
        return OperatorAction.COMPLETE_MFA
    if state in {
        PageState.OBSERVATION_UNAVAILABLE,
        PageState.CAPTCHA,
        PageState.BOT_WALL,
    }:
        return OperatorAction.RETRY_LATER
    if state in {PageState.EXTERNAL, PageState.PROHIBITED, PageState.UNSUPPORTED}:
        return OperatorAction.MAINTAIN_CODE
    return OperatorAction.NONE


def operator_action_for_reason(reason: TerminalBrowserReason) -> OperatorAction:
    """Return deterministic user guidance for one canonical terminal code."""

    if reason is TerminalBrowserReason.AUTHENTICATION_REQUIRED:
        return OperatorAction.CONNECT
    if reason is TerminalBrowserReason.MFA_REQUIRED:
        return OperatorAction.COMPLETE_MFA
    if reason in {
        TerminalBrowserReason.OBSERVATION_UNAVAILABLE,
        TerminalBrowserReason.BOT_WALL,
        TerminalBrowserReason.PROVIDER_AUTHENTICATION,
        TerminalBrowserReason.PROVIDER_UNAVAILABLE,
        TerminalBrowserReason.PROVIDER_RATE_LIMIT,
        TerminalBrowserReason.CALLER_REVOKED,
        TerminalBrowserReason.TIME_LIMIT,
        TerminalBrowserReason.JOB_COST_LIMIT,
        TerminalBrowserReason.DAILY_COST_LIMIT,
        TerminalBrowserReason.MODEL_PRICING_UNAVAILABLE,
        TerminalBrowserReason.MODEL_PROFILE_UNQUALIFIED,
        TerminalBrowserReason.MODEL_NOT_APPROVED,
        TerminalBrowserReason.INVALID_PROVIDER_RESPONSE,
        TerminalBrowserReason.COST_ACCOUNTING_ERROR,
        TerminalBrowserReason.CLOCK_ROLLBACK,
        TerminalBrowserReason.INFRASTRUCTURE_FAILURE,
    }:
        return OperatorAction.RETRY_LATER
    if reason in {
        TerminalBrowserReason.UNSUPPORTED_PAGE,
        TerminalBrowserReason.UNRESOLVED_AMBIGUITY,
        TerminalBrowserReason.CODE_MAINTENANCE_REQUIRED,
    }:
        return OperatorAction.MAINTAIN_CODE
    return OperatorAction.NONE
