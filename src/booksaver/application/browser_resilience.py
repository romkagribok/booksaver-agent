"""Application policy for DOM-step coverage and protected-first page state.

Deterministic known outcomes terminate before an adaptive model session exists.
Only a genuinely ambiguous fresh observation is admitted to the Sonnet/Opus
classification policy, and a model classification never creates code proof.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from enum import Enum
from typing import Protocol

from booksaver.application.model_policy import (
    AdaptiveModelSession,
    AdmittedModelAttempt,
    BrowserJobCostBudget,
)
from booksaver.domain.agent import LLMUsage
from booksaver.domain.browser_resilience import (
    PROTECTED_PAGE_STATES,
    AdaptiveRecoveryPolicy,
    CodeVerificationReceipt,
    DomCapability,
    DomJourney,
    DomStepDefinition,
    DomStepId,
    DomStepRegistry,
    EvidenceCategory,
    EvidenceReference,
    FreshPageObservation,
    ModelStopTerminalMapping,
    OperatorAction,
    PageState,
    PageStateClassification,
    PageStateResolution,
    PageStateSource,
    SemanticSchema,
    StateTerminalMapping,
    TerminalBrowserReason,
    operator_action_for,
)
from booksaver.domain.model_policy import (
    EscalationTrigger,
    ModelAttemptOutcome,
    ModelRole,
    ModelStopReason,
    TokenEnvelope,
)

PAGE_STATE_PROMPT_VERSION = "booking-page-state-v2"
DEFAULT_CLASSIFICATION_ENVELOPE = TokenEnvelope(12_000, 512)
DEFAULT_CLASSIFICATION_CONFIDENCE = 0.80

_POSSIBLE_URL = re.compile(r"(?:https?://|www\.|\?[^\s=]+=[^\s]+)", re.IGNORECASE)
_SAFE_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_CONTROL_ROLE = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
_SECRET_MATERIAL = re.compile(
    r"(?:cookie\s*:|authorization\s*:|bearer\s+[A-Za-z0-9._~-]{8,})",
    re.IGNORECASE,
)
_MAX_TITLE_LENGTH = 256
_MAX_VISIBLE_TEXT_LENGTH = 6_000
_MAX_CONTROL_LABEL_LENGTH = 256
_MAX_CONTROLS = 80


REMOTE_AUTH_DOM_STEPS: tuple[DomStepId, ...] = ()
SESSION_VALIDATION_DOM_STEPS = (DomStepId.SESSION_VALIDATION,)
ACCOUNT_INVENTORY_DOM_STEPS = (
    DomStepId.INVENTORY_ENTRY,
    DomStepId.INVENTORY_READINESS,
    DomStepId.INVENTORY_SCOPE,
    DomStepId.INVENTORY_PAGINATION,
    DomStepId.INVENTORY_DETAIL,
    DomStepId.INVENTORY_EXTRACTION,
    DomStepId.INVENTORY_COMPLETENESS,
)
PRICE_SEARCH_DOM_STEPS = (
    DomStepId.PRICE_SEARCH_QUERY_SUBMISSION,
    DomStepId.PRICE_SEARCH_RESULTS,
    DomStepId.PRICE_CONSENT_OVERLAY,
    DomStepId.PRICE_PROPERTY_LOCATE,
    DomStepId.PRICE_PROPERTY_OPEN,
    DomStepId.PRICE_CONTEXT_VERIFY,
    DomStepId.PRICE_ROOM_RATE_READINESS,
    DomStepId.PRICE_CURRENCY_ALIGN,
    DomStepId.PRICE_SNAPSHOT,
    DomStepId.PRICE_OFFER_EXTRACTION,
)
PRODUCTION_DOM_STEPS = (
    *REMOTE_AUTH_DOM_STEPS,
    *SESSION_VALIDATION_DOM_STEPS,
    *ACCOUNT_INVENTORY_DOM_STEPS,
    *PRICE_SEARCH_DOM_STEPS,
)


_MODEL_STOP_REASONS: dict[ModelStopReason, TerminalBrowserReason] = {
    ModelStopReason.AUTHENTICATION_REQUIRED: TerminalBrowserReason.AUTHENTICATION_REQUIRED,
    ModelStopReason.MFA_REQUIRED: TerminalBrowserReason.MFA_REQUIRED,
    ModelStopReason.CAPTCHA: TerminalBrowserReason.BOT_WALL,
    ModelStopReason.BOT_WALL: TerminalBrowserReason.BOT_WALL,
    ModelStopReason.PROTECTED_DESTINATION: TerminalBrowserReason.BLOCKED_DESTINATION,
    ModelStopReason.PROHIBITED_ACTION: TerminalBrowserReason.PROHIBITED_ACTION,
    ModelStopReason.DETERMINISTIC_REJECTION: TerminalBrowserReason.DETERMINISTIC_REJECTION,
    ModelStopReason.OBSERVATION_UNAVAILABLE: TerminalBrowserReason.OBSERVATION_UNAVAILABLE,
    ModelStopReason.PROVIDER_AUTHENTICATION: TerminalBrowserReason.PROVIDER_AUTHENTICATION,
    ModelStopReason.PROVIDER_UNAVAILABLE: TerminalBrowserReason.PROVIDER_UNAVAILABLE,
    ModelStopReason.PROVIDER_RATE_LIMIT: TerminalBrowserReason.PROVIDER_RATE_LIMIT,
    ModelStopReason.CALLER_REVOKED: TerminalBrowserReason.CALLER_REVOKED,
    ModelStopReason.TIME_LIMIT: TerminalBrowserReason.TIME_LIMIT,
    ModelStopReason.JOB_COST_LIMIT: TerminalBrowserReason.JOB_COST_LIMIT,
    ModelStopReason.DAILY_COST_LIMIT: TerminalBrowserReason.DAILY_COST_LIMIT,
    ModelStopReason.MODEL_PRICING_UNAVAILABLE: TerminalBrowserReason.MODEL_PRICING_UNAVAILABLE,
    ModelStopReason.MODEL_PROFILE_UNQUALIFIED: TerminalBrowserReason.MODEL_PROFILE_UNQUALIFIED,
    ModelStopReason.MODEL_NOT_APPROVED: TerminalBrowserReason.MODEL_NOT_APPROVED,
    ModelStopReason.INVALID_PROVIDER_RESPONSE: TerminalBrowserReason.INVALID_PROVIDER_RESPONSE,
    ModelStopReason.OPUS_EXHAUSTED: TerminalBrowserReason.UNRESOLVED_AMBIGUITY,
    ModelStopReason.COST_ACCOUNTING_ERROR: TerminalBrowserReason.COST_ACCOUNTING_ERROR,
    ModelStopReason.CLOCK_ROLLBACK: TerminalBrowserReason.CLOCK_ROLLBACK,
}


def _state_mappings(
    supported_states: frozenset[PageState],
) -> tuple[StateTerminalMapping, ...]:
    exact = {
        PageState.OBSERVATION_UNAVAILABLE: TerminalBrowserReason.OBSERVATION_UNAVAILABLE,
        PageState.AUTHENTICATION_REQUIRED: TerminalBrowserReason.AUTHENTICATION_REQUIRED,
        PageState.MFA_REQUIRED: TerminalBrowserReason.MFA_REQUIRED,
        PageState.CAPTCHA: TerminalBrowserReason.BOT_WALL,
        PageState.BOT_WALL: TerminalBrowserReason.BOT_WALL,
        PageState.EXTERNAL: TerminalBrowserReason.BLOCKED_DESTINATION,
        PageState.PROHIBITED: TerminalBrowserReason.PROHIBITED_ACTION,
        PageState.AUTHENTICATED_CANDIDATE: TerminalBrowserReason.CODE_VERIFICATION_REQUIRED,
        PageState.UNSUPPORTED: TerminalBrowserReason.UNSUPPORTED_PAGE,
        PageState.AMBIGUOUS: TerminalBrowserReason.UNRESOLVED_AMBIGUITY,
    }
    for state in (
        PageState.VERIFIED_AUTHENTICATED,
        PageState.INVENTORY,
        PageState.SEARCH_RESULTS,
        PageState.PROPERTY,
    ):
        exact[state] = (
            TerminalBrowserReason.POSTCONDITION_SATISFIED
            if state in supported_states
            else TerminalBrowserReason.UNSUPPORTED_PAGE
        )
    return tuple(StateTerminalMapping(state, exact[state]) for state in PageState)


def _model_stop_mappings() -> tuple[ModelStopTerminalMapping, ...]:
    if set(_MODEL_STOP_REASONS) != set(ModelStopReason):
        missing = sorted(reason.value for reason in set(ModelStopReason) - set(_MODEL_STOP_REASONS))
        raise RuntimeError(f"model-stop mapping is incomplete: {missing}")
    return tuple(
        ModelStopTerminalMapping(stop, _MODEL_STOP_REASONS[stop]) for stop in ModelStopReason
    )


def _step(
    step_id: DomStepId,
    journey: DomJourney,
    postcondition: str,
    *,
    supported_states: frozenset[PageState],
    schema: SemanticSchema = SemanticSchema.PAGE_STATE,
    policy: AdaptiveRecoveryPolicy = AdaptiveRecoveryPolicy.DIAGNOSIS_ONLY,
    capabilities: frozenset[DomCapability] = frozenset(),
) -> DomStepDefinition:
    return DomStepDefinition(
        step_id=step_id,
        journey=journey,
        deterministic_postcondition=postcondition,
        safe_capabilities=capabilities,
        protected_states=PROTECTED_PAGE_STATES,
        supported_states=supported_states,
        semantic_schema=schema,
        recovery_policy=policy,
        state_mappings=_state_mappings(supported_states),
        model_stop_mappings=_model_stop_mappings(),
    )


_AUTH_STATES = frozenset({PageState.VERIFIED_AUTHENTICATED, PageState.INVENTORY})
_INVENTORY_STATE = frozenset({PageState.INVENTORY})
_RESULTS_STATE = frozenset({PageState.SEARCH_RESULTS})
_PROPERTY_STATE = frozenset({PageState.PROPERTY})
_READ = frozenset({DomCapability.INSPECT_VISIBLE_STRUCTURE})
_NAVIGATE = frozenset(
    {
        DomCapability.INSPECT_VISIBLE_STRUCTURE,
        DomCapability.NAVIGATE_APPROVED_READ_ONLY,
    }
)
_ACTIVATE = frozenset(
    {
        DomCapability.INSPECT_VISIBLE_STRUCTURE,
        DomCapability.ACTIVATE_READ_ONLY_CONTROL,
    }
)
_INTERPRET = frozenset(
    {
        DomCapability.INSPECT_VISIBLE_STRUCTURE,
        DomCapability.INTERPRET_VISIBLE_FACTS,
    }
)


DOM_STEP_REGISTRY = DomStepRegistry(
    (
        _step(
            DomStepId.REMOTE_AUTH_SESSION_CAPTURE,
            DomJourney.REMOTE_AUTH,
            "fresh_supported_account_proof",
            supported_states=_AUTH_STATES,
        ),
        _step(
            DomStepId.SESSION_VALIDATION,
            DomJourney.SESSION_VALIDATION,
            "fresh_supported_session_proof",
            supported_states=_AUTH_STATES,
        ),
        _step(
            DomStepId.INVENTORY_ENTRY,
            DomJourney.ACCOUNT_INVENTORY,
            "approved_inventory_destination",
            supported_states=_INVENTORY_STATE,
            policy=AdaptiveRecoveryPolicy.GUARDED_READ_ONLY,
            capabilities=_NAVIGATE,
        ),
        _step(
            DomStepId.INVENTORY_READINESS,
            DomJourney.ACCOUNT_INVENTORY,
            "inventory_structure_ready",
            supported_states=_INVENTORY_STATE,
            schema=SemanticSchema.INVENTORY_STRUCTURE,
            policy=AdaptiveRecoveryPolicy.GUARDED_READ_ONLY,
            capabilities=_READ,
        ),
        _step(
            DomStepId.INVENTORY_SCOPE,
            DomJourney.ACCOUNT_INVENTORY,
            "inventory_scope_verified",
            supported_states=_INVENTORY_STATE,
            schema=SemanticSchema.INVENTORY_STRUCTURE,
            policy=AdaptiveRecoveryPolicy.GUARDED_READ_ONLY,
            capabilities=_ACTIVATE,
        ),
        _step(
            DomStepId.INVENTORY_PAGINATION,
            DomJourney.ACCOUNT_INVENTORY,
            "inventory_page_progress_verified",
            supported_states=_INVENTORY_STATE,
            schema=SemanticSchema.INVENTORY_STRUCTURE,
            policy=AdaptiveRecoveryPolicy.GUARDED_READ_ONLY,
            capabilities=_ACTIVATE,
        ),
        _step(
            DomStepId.INVENTORY_DETAIL,
            DomJourney.ACCOUNT_INVENTORY,
            "inventory_detail_verified",
            supported_states=_INVENTORY_STATE,
            schema=SemanticSchema.INVENTORY_STRUCTURE,
            policy=AdaptiveRecoveryPolicy.GUARDED_READ_ONLY,
            capabilities=frozenset(
                {
                    DomCapability.INSPECT_VISIBLE_STRUCTURE,
                    DomCapability.NAVIGATE_APPROVED_READ_ONLY,
                    DomCapability.ADOPT_APPROVED_READ_ONLY_POPUP,
                }
            ),
        ),
        _step(
            DomStepId.INVENTORY_EXTRACTION,
            DomJourney.ACCOUNT_INVENTORY,
            "inventory_observations_validated",
            supported_states=_INVENTORY_STATE,
            schema=SemanticSchema.INVENTORY_RESERVATIONS,
            policy=AdaptiveRecoveryPolicy.GUARDED_READ_ONLY,
            capabilities=_INTERPRET,
        ),
        _step(
            DomStepId.INVENTORY_COMPLETENESS,
            DomJourney.ACCOUNT_INVENTORY,
            "inventory_completeness_proven_by_code",
            supported_states=_INVENTORY_STATE,
            schema=SemanticSchema.INVENTORY_STRUCTURE,
        ),
        _step(
            DomStepId.PRICE_SEARCH_QUERY_SUBMISSION,
            DomJourney.PRICE_SEARCH,
            "trusted_results_query_submitted",
            supported_states=_RESULTS_STATE,
            schema=SemanticSchema.SEARCH_STRUCTURE,
            policy=AdaptiveRecoveryPolicy.GUARDED_READ_ONLY,
            capabilities=_NAVIGATE,
        ),
        _step(
            DomStepId.PRICE_SEARCH_RESULTS,
            DomJourney.PRICE_SEARCH,
            "search_results_ready",
            supported_states=_RESULTS_STATE,
            schema=SemanticSchema.SEARCH_STRUCTURE,
            policy=AdaptiveRecoveryPolicy.GUARDED_READ_ONLY,
            capabilities=_READ,
        ),
        _step(
            DomStepId.PRICE_CONSENT_OVERLAY,
            DomJourney.PRICE_SEARCH,
            "consent_overlay_not_blocking",
            supported_states=frozenset({PageState.SEARCH_RESULTS, PageState.PROPERTY}),
            policy=AdaptiveRecoveryPolicy.GUARDED_READ_ONLY,
            capabilities=frozenset(
                {
                    DomCapability.INSPECT_VISIBLE_STRUCTURE,
                    DomCapability.DISMISS_CONSENT,
                }
            ),
        ),
        _step(
            DomStepId.PRICE_PROPERTY_LOCATE,
            DomJourney.PRICE_SEARCH,
            "trusted_property_result_identified",
            supported_states=_RESULTS_STATE,
            schema=SemanticSchema.SEARCH_STRUCTURE,
            policy=AdaptiveRecoveryPolicy.GUARDED_READ_ONLY,
            capabilities=_INTERPRET,
        ),
        _step(
            DomStepId.PRICE_PROPERTY_OPEN,
            DomJourney.PRICE_SEARCH,
            "approved_property_destination",
            supported_states=_PROPERTY_STATE,
            schema=SemanticSchema.PROPERTY_CONTEXT,
            policy=AdaptiveRecoveryPolicy.GUARDED_READ_ONLY,
            capabilities=frozenset(
                {
                    DomCapability.INSPECT_VISIBLE_STRUCTURE,
                    DomCapability.ACTIVATE_READ_ONLY_CONTROL,
                    DomCapability.ADOPT_APPROVED_READ_ONLY_POPUP,
                }
            ),
        ),
        _step(
            DomStepId.PRICE_CONTEXT_VERIFY,
            DomJourney.PRICE_SEARCH,
            "trusted_property_context_verified",
            supported_states=_PROPERTY_STATE,
            schema=SemanticSchema.PROPERTY_CONTEXT,
        ),
        _step(
            DomStepId.PRICE_ROOM_RATE_READINESS,
            DomJourney.PRICE_SEARCH,
            "room_rate_content_ready",
            supported_states=_PROPERTY_STATE,
            schema=SemanticSchema.ROOM_RATE_STRUCTURE,
            policy=AdaptiveRecoveryPolicy.GUARDED_READ_ONLY,
            capabilities=_ACTIVATE,
        ),
        _step(
            DomStepId.PRICE_CURRENCY_ALIGN,
            DomJourney.PRICE_SEARCH,
            "requested_currency_verified",
            supported_states=_PROPERTY_STATE,
            schema=SemanticSchema.CURRENCY_STATE,
            policy=AdaptiveRecoveryPolicy.GUARDED_READ_ONLY,
            capabilities=_ACTIVATE,
        ),
        _step(
            DomStepId.PRICE_SNAPSHOT,
            DomJourney.PRICE_SEARCH,
            "fresh_property_observation_available",
            supported_states=_PROPERTY_STATE,
            policy=AdaptiveRecoveryPolicy.GUARDED_READ_ONLY,
            capabilities=_READ,
        ),
        _step(
            DomStepId.PRICE_OFFER_EXTRACTION,
            DomJourney.PRICE_SEARCH,
            "offer_facts_validated",
            supported_states=_PROPERTY_STATE,
            schema=SemanticSchema.OFFER_FACTS,
            policy=AdaptiveRecoveryPolicy.GUARDED_READ_ONLY,
            capabilities=_INTERPRET,
        ),
    )
)


def validate_declared_dom_step_coverage(
    declared_by_workflow: Mapping[str, tuple[DomStepId, ...]],
    *,
    registry: DomStepRegistry = DOM_STEP_REGISTRY,
) -> None:
    """Require production workflow declarations to match registry membership.

    The declarations come from the workflow modules that own the actual DOM
    seams, rather than from registry-adjacent constants.  The error identifies
    both the stable step and owning workflow so a newly added seam cannot hide
    behind an application-only list.
    """

    owners: dict[DomStepId, list[str]] = {}
    repeated_within: dict[str, list[str]] = {}
    for workflow, declared in declared_by_workflow.items():
        duplicates = sorted({step.value for step in declared if declared.count(step) > 1})
        if duplicates:
            repeated_within[workflow] = duplicates
        for step in set(declared):
            owners.setdefault(step, []).append(workflow)

    declared_steps = set(owners)
    expected_steps = set(PRODUCTION_DOM_STEPS)
    if not expected_steps.issubset(registry.step_ids):
        undefined = sorted(step.value for step in expected_steps - registry.step_ids)
        raise ValueError(f"DOM workflow registry definitions missing: {undefined}")
    missing = sorted(step.value for step in expected_steps - declared_steps)
    extra = sorted(step.value for step in declared_steps - expected_steps)
    cross_workflow_duplicates = {
        step.value: sorted(step_owners)
        for step, step_owners in owners.items()
        if len(step_owners) > 1
    }
    if missing or extra or repeated_within or cross_workflow_duplicates:
        raise ValueError(
            "DOM workflow coverage mismatch: "
            f"missing={missing}; extra={extra}; "
            f"duplicates_within={repeated_within}; "
            f"duplicates_across={cross_workflow_duplicates}"
        )


class DeterministicPageClassifier:
    """Classify one fresh allowlisted observation using protected precedence."""

    def classify(
        self,
        observation: FreshPageObservation,
        *,
        supported_states: frozenset[PageState] | None = None,
    ) -> PageStateClassification:
        evidence = observation.evidence
        state = self._state(evidence, supported_states=supported_states)
        confidence = 0.0 if state is PageState.AMBIGUOUS else 1.0
        return PageStateClassification(
            state=state,
            confidence=confidence,
            evidence=evidence,
            evidence_references=observation.evidence_references,
            operator_action=operator_action_for(state),
            source=PageStateSource.DETERMINISTIC,
            observation_id=observation.observation_id,
        )

    @staticmethod
    def _state(
        evidence: frozenset[EvidenceCategory],
        *,
        supported_states: frozenset[PageState] | None,
    ) -> PageState:
        if EvidenceCategory.OBSERVATION_UNAVAILABLE in evidence:
            return PageState.OBSERVATION_UNAVAILABLE
        if EvidenceCategory.EXTERNAL_DESTINATION in evidence:
            return PageState.EXTERNAL
        if EvidenceCategory.PROHIBITED_OR_MUTATING_DESTINATION in evidence:
            return PageState.PROHIBITED
        if EvidenceCategory.BOT_WALL in evidence:
            return PageState.BOT_WALL
        if EvidenceCategory.CAPTCHA_CHALLENGE in evidence:
            return PageState.CAPTCHA
        if EvidenceCategory.MFA_CONTROL in evidence:
            return PageState.MFA_REQUIRED
        if EvidenceCategory.CREDENTIAL_CONTROL in evidence:
            return PageState.AUTHENTICATION_REQUIRED

        structural = {
            EvidenceCategory.SUPPORTED_ACCOUNT_STRUCTURE: PageState.VERIFIED_AUTHENTICATED,
            EvidenceCategory.SUPPORTED_INVENTORY_STRUCTURE: PageState.INVENTORY,
            EvidenceCategory.SUPPORTED_SEARCH_RESULTS_STRUCTURE: PageState.SEARCH_RESULTS,
            EvidenceCategory.SUPPORTED_PROPERTY_STRUCTURE: PageState.PROPERTY,
        }
        candidates = {state for marker, state in structural.items() if marker in evidence}
        if supported_states is not None:
            expected = candidates.intersection(supported_states)
            if len(expected) == 1:
                return next(iter(expected))
            if len(expected) > 1:
                return PageState.AMBIGUOUS
            if candidates:
                return PageState.UNSUPPORTED
        elif len(candidates) == 1:
            return next(iter(candidates))
        elif len(candidates) > 1:
            return PageState.AMBIGUOUS

        # An unrecognized layout is the primary DOM-drift ambiguity case.  It
        # must reach bounded classification rather than being treated as a
        # conclusively unsupported business state.
        if EvidenceCategory.UNSUPPORTED_PAGE_STRUCTURE in evidence:
            return PageState.AMBIGUOUS
        return PageState.AMBIGUOUS


@dataclass(frozen=True, slots=True)
class VisibleControlEvidence:
    """Ephemeral role and label only; never a selector, href, or typed value."""

    reference: str
    role: str
    label: str

    def __post_init__(self) -> None:
        if not _SAFE_IDENTIFIER.fullmatch(self.reference):
            raise ValueError("control reference must be a bounded machine identifier")
        if not _CONTROL_ROLE.fullmatch(self.role):
            raise ValueError("control role must be a bounded machine label")
        if not self.label or len(self.label) > _MAX_CONTROL_LABEL_LENGTH:
            raise ValueError("control label must be present and bounded")
        if _POSSIBLE_URL.search(self.label):
            raise ValueError("control labels cannot contain URLs or query strings")


@dataclass(frozen=True, slots=True)
class PageClassificationEvidence:
    """Bounded current-page evidence passed ephemerally to a classifier.

    This request is deliberately separate from persisted classifications.  It
    contains no selector, script, raw URL, href, control value, cookie, or
    screenshot.  Adapters must omit text and controls containing credentials
    or other typed values before constructing it.
    """

    observation_id: str
    title: str
    visible_text: str
    controls: tuple[VisibleControlEvidence, ...] = ()
    screenshot_allowed: bool = False

    def __post_init__(self) -> None:
        if not _SAFE_IDENTIFIER.fullmatch(self.observation_id):
            raise ValueError("observation_id must be a bounded machine code")
        if len(self.title) > _MAX_TITLE_LENGTH:
            raise ValueError("classification title is too long")
        if len(self.visible_text) > _MAX_VISIBLE_TEXT_LENGTH:
            raise ValueError("classification visible text is too long")
        if len(self.controls) > _MAX_CONTROLS:
            raise ValueError("classification contains too many controls")
        references = tuple(control.reference for control in self.controls)
        if len(set(references)) != len(references):
            raise ValueError("classification control references must be unique")
        if _POSSIBLE_URL.search(self.title) or _POSSIBLE_URL.search(self.visible_text):
            raise ValueError("classification evidence cannot contain URLs or query strings")
        if _SECRET_MATERIAL.search(self.title) or _SECRET_MATERIAL.search(self.visible_text):
            raise ValueError("classification evidence cannot contain secrets")
        if self.screenshot_allowed:
            raise ValueError("page-state classification never accepts screenshots")


@dataclass(frozen=True, slots=True)
class ModelPageStateDecision:
    state: PageState
    confidence: float
    evidence: frozenset[EvidenceCategory]
    evidence_references: tuple[EvidenceReference, ...]
    operator_action: OperatorAction

    def __post_init__(self) -> None:
        if isinstance(self.confidence, bool) or not 0.0 <= self.confidence <= 1.0:
            raise ValueError("model confidence must be between zero and one")
        if any(ref.category not in self.evidence for ref in self.evidence_references):
            raise ValueError("model references must name model evidence")
        state = (
            PageState.AUTHENTICATED_CANDIDATE
            if self.state is PageState.VERIFIED_AUTHENTICATED
            else self.state
        )
        if self.operator_action is not operator_action_for(state):
            raise ValueError("model operator action must match the classified state")

    def classification(
        self,
        *,
        source: PageStateSource,
        observation_id: str,
    ) -> PageStateClassification:
        state = (
            PageState.AUTHENTICATED_CANDIDATE
            if self.state is PageState.VERIFIED_AUTHENTICATED
            else self.state
        )
        return PageStateClassification(
            state=state,
            confidence=self.confidence,
            evidence=self.evidence,
            evidence_references=self.evidence_references,
            operator_action=(
                OperatorAction.NONE
                if state is PageState.AUTHENTICATED_CANDIDATE
                else self.operator_action
            ),
            source=source,
            observation_id=observation_id,
        )


class PageClassifierProviderFailure(Enum):
    AUTHENTICATION = "authentication"
    RATE_LIMIT = "rate_limit"
    UNAVAILABLE = "unavailable"
    TRANSPORT = "transport"


@dataclass(frozen=True, slots=True)
class ModelClassifierCall:
    decision: ModelPageStateDecision | None = None
    stop_reason: ModelStopReason | None = None
    provider_failure: PageClassifierProviderFailure | None = None
    usage: LLMUsage | None = None
    latency_ms: int = 0
    schema_valid: bool = True

    def __post_init__(self) -> None:
        if self.latency_ms < 0:
            raise ValueError("classification latency cannot be negative")
        terminal_values = sum(
            item is not None for item in (self.decision, self.stop_reason, self.provider_failure)
        )
        if terminal_values > 1:
            raise ValueError("model call must contain at most one result or failure")
        if not self.schema_valid and terminal_values:
            raise ValueError("an invalid schema cannot carry a trusted decision or stop")
        if self.schema_valid and not terminal_values:
            raise ValueError("a schema-valid call requires a decision or typed failure")

    @property
    def mapped_stop_reason(self) -> ModelStopReason | None:
        if self.stop_reason is not None:
            return self.stop_reason
        if self.provider_failure is None:
            return None
        return {
            PageClassifierProviderFailure.AUTHENTICATION: (ModelStopReason.PROVIDER_AUTHENTICATION),
            PageClassifierProviderFailure.RATE_LIMIT: ModelStopReason.PROVIDER_RATE_LIMIT,
            PageClassifierProviderFailure.UNAVAILABLE: ModelStopReason.PROVIDER_UNAVAILABLE,
            PageClassifierProviderFailure.TRANSPORT: ModelStopReason.PROVIDER_UNAVAILABLE,
        }[self.provider_failure]


class ModelPageStateClassifier(Protocol):
    def classify(
        self,
        *,
        step: DomStepDefinition,
        observation: FreshPageObservation,
        evidence: PageClassificationEvidence,
        attempt: AdmittedModelAttempt,
    ) -> ModelClassifierCall: ...


class PageStateResolver:
    """Resolve protected states exactly and spend only on current ambiguity."""

    def __init__(
        self,
        model_classifier: ModelPageStateClassifier,
        *,
        registry: DomStepRegistry = DOM_STEP_REGISTRY,
        deterministic_classifier: DeterministicPageClassifier | None = None,
        confidence_threshold: float = DEFAULT_CLASSIFICATION_CONFIDENCE,
        envelope: TokenEnvelope = DEFAULT_CLASSIFICATION_ENVELOPE,
    ) -> None:
        if not 0.0 <= confidence_threshold <= 1.0:
            raise ValueError("confidence threshold must be between zero and one")
        self._model_classifier = model_classifier
        self._registry = registry
        self._deterministic = deterministic_classifier or DeterministicPageClassifier()
        self._confidence_threshold = confidence_threshold
        self._envelope = envelope

    def resolve(
        self,
        *,
        step_id: DomStepId,
        observation: FreshPageObservation,
        classification_evidence: PageClassificationEvidence | None,
        budget_factory: Callable[[], BrowserJobCostBudget],
    ) -> PageStateResolution:
        step = self._registry.definition(step_id)
        deterministic = self._deterministic.classify(
            observation, supported_states=step.supported_states
        )
        if deterministic.state is not PageState.AMBIGUOUS:
            return self._deterministic_resolution(step, observation, deterministic)

        if classification_evidence is None:
            return PageStateResolution(
                classification=deterministic,
                terminal_reason=TerminalBrowserReason.OBSERVATION_UNAVAILABLE,
            )
        if classification_evidence.observation_id != observation.observation_id:
            raise ValueError("classification evidence must match the fresh observation")

        budget = budget_factory()
        session = AdaptiveModelSession(
            role=ModelRole.CLASSIFICATION,
            prompt_version=PAGE_STATE_PROMPT_VERSION,
            budget=budget,
        )
        first = session.start(self._envelope)
        if first.stop_reason is not None:
            return PageStateResolution(
                classification=deterministic,
                terminal_reason=step.reason_for_model_stop(first.stop_reason),
                model_stop_reason=first.stop_reason,
            )
        assert first.attempt is not None
        sonnet = self._call_and_reconcile(
            budget=budget,
            step=step,
            observation=observation,
            evidence=classification_evidence,
            attempt=first.attempt,
        )
        sonnet_resolution = self._model_resolution(
            step,
            observation,
            sonnet,
            source=PageStateSource.SONNET,
        )
        if sonnet_resolution is not None:
            return sonnet_resolution

        trigger = EscalationTrigger.UNRESOLVED_LOW_CONFIDENCE
        if not sonnet.schema_valid:
            primary_retry = session.continue_primary(self._envelope)
            if primary_retry.stop_reason is not None:
                return PageStateResolution(
                    classification=deterministic,
                    terminal_reason=step.reason_for_model_stop(primary_retry.stop_reason),
                    model_stop_reason=primary_retry.stop_reason,
                )
            assert primary_retry.attempt is not None
            retried_sonnet = self._call_and_reconcile(
                budget=budget,
                step=step,
                observation=observation,
                evidence=classification_evidence,
                attempt=primary_retry.attempt,
            )
            retried_resolution = self._model_resolution(
                step,
                observation,
                retried_sonnet,
                source=PageStateSource.SONNET,
            )
            if retried_resolution is not None:
                return retried_resolution
            trigger = (
                EscalationTrigger.REPEATED_INVALID_SCHEMA
                if not retried_sonnet.schema_valid
                else EscalationTrigger.UNRESOLVED_LOW_CONFIDENCE
            )

        second = session.escalate(trigger, self._envelope)
        if second.stop_reason is not None:
            return PageStateResolution(
                classification=deterministic,
                terminal_reason=step.reason_for_model_stop(second.stop_reason),
                model_stop_reason=second.stop_reason,
            )
        assert second.attempt is not None
        opus = self._call_and_reconcile(
            budget=budget,
            step=step,
            observation=observation,
            evidence=classification_evidence,
            attempt=second.attempt,
        )
        opus_resolution = self._model_resolution(
            step,
            observation,
            opus,
            source=PageStateSource.OPUS,
        )
        if opus_resolution is not None:
            return opus_resolution
        return PageStateResolution(
            classification=deterministic,
            terminal_reason=step.reason_for_model_stop(ModelStopReason.OPUS_EXHAUSTED),
            model_stop_reason=ModelStopReason.OPUS_EXHAUSTED,
        )

    @staticmethod
    def _deterministic_resolution(
        step: DomStepDefinition,
        observation: FreshPageObservation,
        classification: PageStateClassification,
    ) -> PageStateResolution:
        reason = step.reason_for_state(classification.state)
        receipt = None
        if reason is TerminalBrowserReason.POSTCONDITION_SATISFIED:
            receipt = CodeVerificationReceipt(
                step_id=step.step_id,
                verified_state=classification.state,
                observation_id=observation.observation_id,
                verified_at=observation.observed_at,
                verifier=step.deterministic_postcondition,
            )
        return PageStateResolution(classification, reason, receipt)

    def _call_and_reconcile(
        self,
        *,
        budget: BrowserJobCostBudget,
        step: DomStepDefinition,
        observation: FreshPageObservation,
        evidence: PageClassificationEvidence,
        attempt: AdmittedModelAttempt,
    ) -> ModelClassifierCall:
        try:
            result = self._model_classifier.classify(
                step=step,
                observation=observation,
                evidence=evidence,
                attempt=attempt,
            )
        except Exception:
            budget.reconcile(
                attempt,
                usage=None,
                latency_ms=0,
                outcome=ModelAttemptOutcome.PROVIDER_FAILED,
            )
            return ModelClassifierCall(stop_reason=ModelStopReason.PROVIDER_UNAVAILABLE)

        if result.mapped_stop_reason is not None:
            outcome = ModelAttemptOutcome.PROVIDER_FAILED
        elif self._is_quality_failure(result):
            outcome = ModelAttemptOutcome.QUALITY_FAILED
        else:
            outcome = ModelAttemptOutcome.DIAGNOSED
        budget.reconcile(
            attempt,
            usage=result.usage,
            latency_ms=result.latency_ms,
            outcome=outcome,
        )
        return result

    def _model_resolution(
        self,
        step: DomStepDefinition,
        observation: FreshPageObservation,
        result: ModelClassifierCall,
        *,
        source: PageStateSource,
    ) -> PageStateResolution | None:
        if result.mapped_stop_reason is not None:
            return PageStateResolution(
                classification=None,
                terminal_reason=step.reason_for_model_stop(result.mapped_stop_reason),
                model_stop_reason=result.mapped_stop_reason,
            )
        if self._is_quality_failure(result):
            return None
        assert result.decision is not None
        classification = result.decision.classification(
            source=source,
            observation_id=observation.observation_id,
        )
        reason = step.reason_for_state(classification.state)
        if reason is TerminalBrowserReason.POSTCONDITION_SATISFIED:
            reason = TerminalBrowserReason.CODE_VERIFICATION_REQUIRED
        return PageStateResolution(classification=classification, terminal_reason=reason)

    def _is_quality_failure(self, result: ModelClassifierCall) -> bool:
        return (
            not result.schema_valid
            or result.decision is None
            or result.decision.confidence < self._confidence_threshold
            or result.decision.state in {PageState.AMBIGUOUS, PageState.UNSUPPORTED}
        )
