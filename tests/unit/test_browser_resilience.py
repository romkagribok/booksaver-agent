from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime

import pytest

from booksaver.application.browser_resilience import (
    DOM_STEP_REGISTRY,
    DeterministicPageClassifier,
    ModelClassifierCall,
    ModelPageStateDecision,
    PageClassificationEvidence,
    PageStateResolver,
    VisibleControlEvidence,
    validate_declared_dom_step_coverage,
)
from booksaver.application.model_policy import BrowserJobCostBudget
from booksaver.domain.agent import LLMUsage
from booksaver.domain.browser_resilience import (
    AdaptiveRecoveryPolicy,
    DomStepId,
    DomStepRegistry,
    EvidenceCategory,
    FreshPageObservation,
    OperatorAction,
    PageState,
    PageStateClassification,
    PageStateSource,
    TerminalBrowserReason,
)
from booksaver.domain.model_policy import (
    AdmissionDecision,
    BrowserJobKind,
    CallerKeyRef,
    CostReconciliation,
    CostReservation,
    EscalationTrigger,
    ModelCostEstimator,
    ModelStopReason,
    ReservationStatus,
)


class _Ledger:
    def __init__(self, *, deny_on_request: int | None = None) -> None:
        self.deny_on_request = deny_on_request
        self.requests = []
        self.reconciliations = []

    def reserve_call(self, request):
        self.requests.append(request)
        if len(self.requests) == self.deny_on_request:
            return AdmissionDecision(denied_reason=ModelStopReason.JOB_COST_LIMIT)
        return AdmissionDecision(
            reservation=CostReservation(
                reservation_id=request.reservation_id,
                job_id=request.job_id,
                utc_date=request.utc_date,
                profile=request.profile,
                reserved_cost=request.reserved_cost,
                status=ReservationStatus.RESERVED,
            )
        )

    def reconcile_call(self, request):
        self.reconciliations.append(request)
        return CostReconciliation(
            reservation_id=request.reservation_id,
            charged_cost=request.charged_cost,
            status=(
                ReservationStatus.CONSERVATIVE
                if request.conservative
                else ReservationStatus.CHARGED
            ),
        )

    def list_attempts(self, job_id):
        return ()


class _ModelClassifier:
    def __init__(self, *results: ModelClassifierCall) -> None:
        self.results = list(results)
        self.calls = []

    def classify(self, *, step, observation, evidence, attempt):
        self.calls.append((step, observation, evidence, attempt))
        return self.results.pop(0)


def _budget(ledger: _Ledger) -> BrowserJobCostBudget:
    return BrowserJobCostBudget(
        job_id="resilience-job-1",
        job_kind=BrowserJobKind.CHECK_NOW,
        caller_key_ref=CallerKeyRef(1, "personal", "encrypted_user_key"),
        ledger=ledger,
        estimator=ModelCostEstimator(),
        clock=lambda: datetime(2026, 8, 13, tzinfo=UTC),
    )


def _observation(*evidence: EvidenceCategory) -> FreshPageObservation:
    return FreshPageObservation(
        observation_id="page-observation-1",
        observed_at=datetime(2026, 8, 13, tzinfo=UTC),
        evidence=frozenset(evidence),
    )


def _classification_evidence() -> PageClassificationEvidence:
    return PageClassificationEvidence(
        observation_id="page-observation-1",
        title="Booking account",
        visible_text="Manage your stay or sign in to continue",
        controls=(VisibleControlEvidence(role="button", label="Continue"),),
    )


class _BudgetFactory:
    def __init__(self, ledger: _Ledger) -> None:
        self.ledger = ledger
        self.calls = 0

    def __call__(self) -> BrowserJobCostBudget:
        self.calls += 1
        return _budget(self.ledger)


def _decision(
    state: PageState,
    *,
    confidence: float = 0.95,
) -> ModelClassifierCall:
    return ModelClassifierCall(
        decision=ModelPageStateDecision(
            state=state,
            confidence=confidence,
            evidence=frozenset(),
            evidence_references=(),
            operator_action={
                PageState.AUTHENTICATION_REQUIRED: OperatorAction.CONNECT,
                PageState.MFA_REQUIRED: OperatorAction.COMPLETE_MFA,
                PageState.CAPTCHA: OperatorAction.RETRY_LATER,
                PageState.BOT_WALL: OperatorAction.RETRY_LATER,
            }.get(state, OperatorAction.NONE),
        ),
        usage=LLMUsage(input_tokens=100, output_tokens=20),
        latency_ms=25,
    )


def test_registry_covers_exact_production_contract_without_legacy_home_form() -> None:
    declared_by_workflow = _production_dom_steps()
    declared = tuple(
        step
        for workflow_steps in declared_by_workflow.values()
        for step in workflow_steps
    )

    validate_declared_dom_step_coverage(declared_by_workflow)
    assert len(declared) == len(set(declared))
    assert set(declared) == set(DomStepId)
    assert DOM_STEP_REGISTRY.step_ids == frozenset(declared)
    assert all("open_home" not in step.value for step in declared)
    assert all("fill_search" not in step.value for step in declared)


def _production_dom_steps() -> dict[str, tuple[DomStepId, ...]]:
    from booksaver.infrastructure.browser import booking_account_inventory, playwright_adapter
    from booksaver.infrastructure.remote_auth import browser_runner
    from booksaver.monitor import search_check_job, search_journey

    return {
        "remote_auth.browser_runner": browser_runner.DOM_STEPS,
        "browser.playwright_adapter": playwright_adapter.DOM_STEPS,
        "browser.booking_account_inventory": booking_account_inventory.DOM_STEPS,
        "monitor.search_journey": search_journey.DOM_STEPS,
        "monitor.search_check_job": search_check_job.DOM_STEPS,
    }


def test_structural_coverage_failure_names_journey_and_step() -> None:
    declared = _production_dom_steps()
    broken = dict(declared)
    broken["monitor.search_journey"] = tuple(
        step
        for step in broken["monitor.search_journey"]
        if step is not DomStepId.PRICE_PROPERTY_OPEN
    )

    with pytest.raises(ValueError) as raised:
        validate_declared_dom_step_coverage(broken)

    assert "price_search.property_open" in str(raised.value)
    assert "missing=" in str(raised.value)


def test_structural_coverage_failure_names_duplicate_workflows() -> None:
    declared = _production_dom_steps()
    broken = dict(declared)
    broken["remote_auth.browser_runner"] = (
        *broken["remote_auth.browser_runner"],
        DomStepId.SESSION_VALIDATION,
    )

    with pytest.raises(ValueError) as raised:
        validate_declared_dom_step_coverage(broken)

    detail = str(raised.value)
    assert "session.validation" in detail
    assert "remote_auth.browser_runner" in detail
    assert "browser.playwright_adapter" in detail


def test_every_definition_has_total_mappings_and_diagnosis_has_no_capability() -> None:
    for definition in DOM_STEP_REGISTRY.definitions:
        assert {item.state for item in definition.state_mappings} == set(PageState)
        assert {item.stop for item in definition.model_stop_mappings} == set(
            ModelStopReason
        )
        if definition.recovery_policy is not AdaptiveRecoveryPolicy.GUARDED_READ_ONLY:
            assert not definition.safe_capabilities


def test_registry_rejects_missing_or_duplicate_steps() -> None:
    with pytest.raises(ValueError, match="coverage mismatch"):
        DomStepRegistry(DOM_STEP_REGISTRY.definitions[:-1])
    duplicate = (*DOM_STEP_REGISTRY.definitions, DOM_STEP_REGISTRY.definitions[0])
    with pytest.raises(ValueError, match="unique"):
        DomStepRegistry(duplicate)


def test_definition_rejects_incomplete_terminal_mapping() -> None:
    original = DOM_STEP_REGISTRY.definition(DomStepId.SESSION_VALIDATION)
    with pytest.raises(ValueError, match="unique and total"):
        replace(original, state_mappings=original.state_mappings[:-1])


def test_login_and_challenge_evidence_outrank_weak_account_chrome() -> None:
    classifier = DeterministicPageClassifier()
    login = classifier.classify(
        _observation(
            EvidenceCategory.WEAK_ACCOUNT_CHROME,
            EvidenceCategory.CREDENTIAL_CONTROL,
        )
    )
    mfa = classifier.classify(
        _observation(
            EvidenceCategory.WEAK_ACCOUNT_CHROME,
            EvidenceCategory.MFA_CONTROL,
        )
    )
    captcha = classifier.classify(
        _observation(
            EvidenceCategory.WEAK_ACCOUNT_CHROME,
            EvidenceCategory.CAPTCHA_CHALLENGE,
        )
    )

    assert login.state is PageState.AUTHENTICATION_REQUIRED
    assert login.operator_action is OperatorAction.CONNECT
    assert mfa.state is PageState.MFA_REQUIRED
    assert captcha.state is PageState.CAPTCHA


@pytest.mark.parametrize(
    ("evidence", "state"),
    [
        (EvidenceCategory.OBSERVATION_UNAVAILABLE, PageState.OBSERVATION_UNAVAILABLE),
        (EvidenceCategory.EXTERNAL_DESTINATION, PageState.EXTERNAL),
        (
            EvidenceCategory.PROHIBITED_OR_MUTATING_DESTINATION,
            PageState.PROHIBITED,
        ),
        (EvidenceCategory.BOT_WALL, PageState.BOT_WALL),
    ],
)
def test_protected_state_classification_is_exact(evidence, state) -> None:
    classification = DeterministicPageClassifier().classify(
        _observation(evidence, EvidenceCategory.WEAK_ACCOUNT_CHROME)
    )
    assert classification.state is state
    assert classification.confidence == 1.0


def test_strong_inventory_is_supported_but_weak_chrome_remains_ambiguous() -> None:
    classifier = DeterministicPageClassifier()
    inventory = classifier.classify(
        _observation(EvidenceCategory.SUPPORTED_INVENTORY_STRUCTURE),
        supported_states=frozenset({PageState.INVENTORY}),
    )
    weak = classifier.classify(_observation(EvidenceCategory.WEAK_ACCOUNT_CHROME))

    assert inventory.state is PageState.INVENTORY
    assert weak.state is PageState.AMBIGUOUS
    assert weak.confidence == 0.0


def test_model_cannot_create_verified_authentication_classification() -> None:
    with pytest.raises(ValueError, match="cannot verify authentication"):
        PageStateClassification(
            state=PageState.VERIFIED_AUTHENTICATED,
            confidence=1.0,
            evidence=frozenset(),
            evidence_references=(),
            operator_action=OperatorAction.NONE,
            source=PageStateSource.SONNET,
            observation_id="observation-1",
        )


def test_known_auth_state_uses_zero_model_calls_and_zero_ledger_rows() -> None:
    ledger = _Ledger()
    model = _ModelClassifier()
    budget_factory = _BudgetFactory(ledger)
    resolution = PageStateResolver(model).resolve(
        step_id=DomStepId.SESSION_VALIDATION,
        observation=_observation(
            EvidenceCategory.WEAK_ACCOUNT_CHROME,
            EvidenceCategory.CREDENTIAL_CONTROL,
        ),
        classification_evidence=_classification_evidence(),
        budget_factory=budget_factory,
    )

    assert resolution.terminal_reason is TerminalBrowserReason.AUTHENTICATION_REQUIRED
    assert resolution.verification_receipt is None
    assert not model.calls
    assert budget_factory.calls == 0
    assert not ledger.requests
    assert not ledger.reconciliations


def test_known_captcha_uses_zero_model_calls_and_never_resolves_budget() -> None:
    ledger = _Ledger()
    model = _ModelClassifier()
    budget_factory = _BudgetFactory(ledger)

    resolution = PageStateResolver(model).resolve(
        step_id=DomStepId.SESSION_VALIDATION,
        observation=_observation(EvidenceCategory.CAPTCHA_CHALLENGE),
        classification_evidence=_classification_evidence(),
        budget_factory=budget_factory,
    )

    assert resolution.terminal_reason is TerminalBrowserReason.BOT_WALL
    assert budget_factory.calls == 0
    assert not model.calls
    assert not ledger.requests


def test_deterministic_supported_page_creates_code_receipt_without_model() -> None:
    ledger = _Ledger()
    model = _ModelClassifier()
    budget_factory = _BudgetFactory(ledger)
    resolution = PageStateResolver(model).resolve(
        step_id=DomStepId.INVENTORY_READINESS,
        observation=_observation(EvidenceCategory.SUPPORTED_INVENTORY_STRUCTURE),
        classification_evidence=_classification_evidence(),
        budget_factory=budget_factory,
    )

    assert resolution.terminal_reason is TerminalBrowserReason.POSTCONDITION_SATISFIED
    assert resolution.verification_receipt is not None
    assert resolution.verification_receipt.verified_state is PageState.INVENTORY
    assert not model.calls
    assert budget_factory.calls == 0
    assert not ledger.requests


def test_ambiguous_state_uses_sonnet_and_model_auth_requires_code_verification() -> None:
    ledger = _Ledger()
    model = _ModelClassifier(_decision(PageState.VERIFIED_AUTHENTICATED))
    budget_factory = _BudgetFactory(ledger)
    resolution = PageStateResolver(model).resolve(
        step_id=DomStepId.SESSION_VALIDATION,
        observation=_observation(EvidenceCategory.WEAK_ACCOUNT_CHROME),
        classification_evidence=_classification_evidence(),
        budget_factory=budget_factory,
    )

    assert resolution.classification is not None
    assert resolution.classification.state is PageState.AUTHENTICATED_CANDIDATE
    assert resolution.classification.source is PageStateSource.SONNET
    assert resolution.terminal_reason is TerminalBrowserReason.CODE_VERIFICATION_REQUIRED
    assert resolution.verification_receipt is None
    assert budget_factory.calls == 1
    assert len(ledger.requests) == 1
    assert len(ledger.reconciliations) == 1


def test_first_invalid_schema_retries_sonnet_and_accepts_valid_retry() -> None:
    ledger = _Ledger()
    model = _ModelClassifier(
        ModelClassifierCall(schema_valid=False),
        _decision(PageState.AUTHENTICATION_REQUIRED),
    )
    budget_factory = _BudgetFactory(ledger)

    resolution = PageStateResolver(model).resolve(
        step_id=DomStepId.SESSION_VALIDATION,
        observation=_observation(EvidenceCategory.WEAK_ACCOUNT_CHROME),
        classification_evidence=_classification_evidence(),
        budget_factory=budget_factory,
    )

    assert resolution.classification is not None
    assert resolution.classification.state is PageState.AUTHENTICATION_REQUIRED
    assert resolution.classification.source is PageStateSource.SONNET
    assert resolution.terminal_reason is TerminalBrowserReason.AUTHENTICATION_REQUIRED
    assert [request.profile.model_id for request in ledger.requests] == [
        "claude-sonnet-5",
        "claude-sonnet-5",
    ]
    assert len(ledger.reconciliations) == 2


def test_two_invalid_sonnet_schemas_escalate_to_opus_and_preserve_auth_reason() -> None:
    ledger = _Ledger()
    model = _ModelClassifier(
        ModelClassifierCall(schema_valid=False),
        ModelClassifierCall(schema_valid=False),
        _decision(PageState.AUTHENTICATION_REQUIRED),
    )
    budget_factory = _BudgetFactory(ledger)
    resolution = PageStateResolver(model).resolve(
        step_id=DomStepId.SESSION_VALIDATION,
        observation=_observation(EvidenceCategory.WEAK_ACCOUNT_CHROME),
        classification_evidence=_classification_evidence(),
        budget_factory=budget_factory,
    )

    assert resolution.classification is not None
    assert resolution.classification.state is PageState.AUTHENTICATION_REQUIRED
    assert resolution.classification.source is PageStateSource.OPUS
    assert resolution.terminal_reason is TerminalBrowserReason.AUTHENTICATION_REQUIRED
    assert budget_factory.calls == 1
    assert [request.profile.model_id for request in ledger.requests] == [
        "claude-sonnet-5",
        "claude-sonnet-5",
        "claude-opus-5",
    ]
    assert [request.trigger for request in ledger.requests] == [
        EscalationTrigger.INITIAL_AMBIGUOUS,
        EscalationTrigger.INITIAL_AMBIGUOUS,
        EscalationTrigger.REPEATED_INVALID_SCHEMA,
    ]
    assert len(ledger.reconciliations) == 3


def test_second_sonnet_admission_denial_is_exact_and_does_not_call_opus() -> None:
    ledger = _Ledger(deny_on_request=2)
    model = _ModelClassifier(ModelClassifierCall(schema_valid=False))
    budget_factory = _BudgetFactory(ledger)

    resolution = PageStateResolver(model).resolve(
        step_id=DomStepId.SESSION_VALIDATION,
        observation=_observation(EvidenceCategory.WEAK_ACCOUNT_CHROME),
        classification_evidence=_classification_evidence(),
        budget_factory=budget_factory,
    )

    assert resolution.terminal_reason is TerminalBrowserReason.JOB_COST_LIMIT
    assert resolution.model_stop_reason is ModelStopReason.JOB_COST_LIMIT
    assert len(model.calls) == 1
    assert [request.profile.model_id for request in ledger.requests] == [
        "claude-sonnet-5",
        "claude-sonnet-5",
    ]
    assert len(ledger.reconciliations) == 1


def test_low_confidence_sonnet_escalates_directly_without_schema_retry() -> None:
    ledger = _Ledger()
    model = _ModelClassifier(
        _decision(PageState.AUTHENTICATION_REQUIRED, confidence=0.50),
        _decision(PageState.AUTHENTICATION_REQUIRED),
    )
    budget_factory = _BudgetFactory(ledger)

    resolution = PageStateResolver(model).resolve(
        step_id=DomStepId.SESSION_VALIDATION,
        observation=_observation(EvidenceCategory.WEAK_ACCOUNT_CHROME),
        classification_evidence=_classification_evidence(),
        budget_factory=budget_factory,
    )

    assert resolution.classification is not None
    assert resolution.classification.source is PageStateSource.OPUS
    assert [request.profile.model_id for request in ledger.requests] == [
        "claude-sonnet-5",
        "claude-opus-5",
    ]
    assert ledger.requests[-1].trigger is EscalationTrigger.UNRESOLVED_LOW_CONFIDENCE


def test_provider_stop_is_exact_and_does_not_trigger_explanation_call() -> None:
    ledger = _Ledger()
    model = _ModelClassifier(
        ModelClassifierCall(stop_reason=ModelStopReason.PROVIDER_RATE_LIMIT)
    )
    budget_factory = _BudgetFactory(ledger)
    resolution = PageStateResolver(model).resolve(
        step_id=DomStepId.SESSION_VALIDATION,
        observation=_observation(EvidenceCategory.WEAK_ACCOUNT_CHROME),
        classification_evidence=_classification_evidence(),
        budget_factory=budget_factory,
    )

    assert resolution.terminal_reason is TerminalBrowserReason.PROVIDER_RATE_LIMIT
    assert resolution.model_stop_reason is ModelStopReason.PROVIDER_RATE_LIMIT
    assert budget_factory.calls == 1
    assert len(model.calls) == 1
    assert len(ledger.requests) == 1
    assert len(ledger.reconciliations) == 1


def test_unknown_layout_is_ambiguous_and_uses_the_lazy_model_path() -> None:
    ledger = _Ledger()
    model = _ModelClassifier(_decision(PageState.AUTHENTICATION_REQUIRED))
    budget_factory = _BudgetFactory(ledger)

    resolution = PageStateResolver(model).resolve(
        step_id=DomStepId.SESSION_VALIDATION,
        observation=_observation(EvidenceCategory.UNSUPPORTED_PAGE_STRUCTURE),
        classification_evidence=_classification_evidence(),
        budget_factory=budget_factory,
    )

    assert resolution.terminal_reason is TerminalBrowserReason.AUTHENTICATION_REQUIRED
    assert budget_factory.calls == 1
    assert len(model.calls) == 1


def test_ambiguous_page_without_ephemeral_evidence_stops_before_key_resolution() -> None:
    ledger = _Ledger()
    model = _ModelClassifier()
    budget_factory = _BudgetFactory(ledger)

    resolution = PageStateResolver(model).resolve(
        step_id=DomStepId.SESSION_VALIDATION,
        observation=_observation(EvidenceCategory.WEAK_ACCOUNT_CHROME),
        classification_evidence=None,
        budget_factory=budget_factory,
    )

    assert resolution.terminal_reason is TerminalBrowserReason.OBSERVATION_UNAVAILABLE
    assert budget_factory.calls == 0
    assert not model.calls


def test_ephemeral_classifier_evidence_rejects_urls_and_screenshots() -> None:
    with pytest.raises(ValueError, match="URLs"):
        PageClassificationEvidence(
            observation_id="observation-1",
            title="Booking",
            visible_text="Continue at https://example.com",
        )
    with pytest.raises(ValueError, match="screenshots"):
        PageClassificationEvidence(
            observation_id="observation-1",
            title="Booking",
            visible_text="Sign in",
            screenshot_allowed=True,
        )


def test_model_decision_rejects_action_that_does_not_match_state() -> None:
    with pytest.raises(ValueError, match="operator action"):
        ModelPageStateDecision(
            state=PageState.AUTHENTICATION_REQUIRED,
            confidence=0.95,
            evidence=frozenset(),
            evidence_references=(),
            operator_action=OperatorAction.NONE,
        )
