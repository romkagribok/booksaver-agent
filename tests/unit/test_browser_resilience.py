from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime

import pytest

from booksaver.application.browser_resilience import (
    ACCOUNT_INVENTORY_DOM_STEPS,
    DOM_STEP_REGISTRY,
    PRICE_SEARCH_DOM_STEPS,
    DeterministicPageClassifier,
    PageClassificationEvidence,
    validate_declared_dom_step_coverage,
)
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
)
from booksaver.domain.model_policy import ModelStopReason


def _observation(*evidence: EvidenceCategory) -> FreshPageObservation:
    return FreshPageObservation(
        observation_id="page-observation-1",
        observed_at=datetime(2026, 8, 13, tzinfo=UTC),
        evidence=frozenset(evidence),
    )


def test_registry_covers_exact_production_contract_without_legacy_home_form() -> None:
    declared_by_workflow = _production_dom_steps()
    declared = tuple(
        step for workflow_steps in declared_by_workflow.values() for step in workflow_steps
    )

    validate_declared_dom_step_coverage(declared_by_workflow)
    assert len(declared) == len(set(declared))
    assert set(declared) == set(DomStepId) - {DomStepId.REMOTE_AUTH_SESSION_CAPTURE}
    assert declared_by_workflow["remote_auth.browser_runner"] == ()
    assert DOM_STEP_REGISTRY.step_ids == frozenset(DomStepId)
    assert DomStepId.REMOTE_AUTH_SESSION_CAPTURE not in declared
    assert all("open_home" not in step.value for step in declared)
    assert all("fill_search" not in step.value for step in declared)


def _production_dom_steps() -> dict[str, tuple[DomStepId, ...]]:
    from booksaver.infrastructure.browser import playwright_adapter
    from booksaver.infrastructure.remote_auth import browser_runner

    # Jev workflows own no DOM seams; their steps stay as the DOM-incident vocabulary.
    return {
        "remote_auth.browser_runner": browser_runner.DOM_STEPS,
        "browser.playwright_adapter": playwright_adapter.DOM_STEPS,
        "incidents.account_inventory": ACCOUNT_INVENTORY_DOM_STEPS,
        "incidents.price_search": PRICE_SEARCH_DOM_STEPS,
    }


def test_structural_coverage_failure_names_journey_and_step() -> None:
    declared = _production_dom_steps()
    broken = dict(declared)
    broken["incidents.price_search"] = tuple(
        step
        for step in broken["incidents.price_search"]
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
        assert {item.stop for item in definition.model_stop_mappings} == set(ModelStopReason)
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
