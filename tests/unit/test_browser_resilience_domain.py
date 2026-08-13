from __future__ import annotations

from datetime import UTC, datetime

import pytest

from booksaver.domain.browser_resilience import (
    CodeVerificationReceipt,
    DiagnosisProvenance,
    DomStepId,
    EvidenceCategory,
    OperatorAction,
    PageState,
    PopupAdoptionReceipt,
    PopupAdoptionResult,
    PopupRefusalReason,
    SemanticFact,
    SemanticFactKey,
    SemanticStepObservation,
    StepVerificationResult,
    StepVerificationStatus,
    TerminalBrowserDiagnosis,
    TerminalBrowserReason,
    VisibleEvidence,
    VisibleEvidenceKind,
)
from booksaver.domain.check_result import (
    CheckResult,
    FailureCode,
    FailureReason,
    failure_code_for_terminal,
)
from booksaver.domain.model_policy import ModelStopReason

NOW = datetime(2026, 8, 13, tzinfo=UTC)


def _visible_excerpt() -> VisibleEvidence:
    return VisibleEvidence(
        evidence_id="visible-1",
        kind=VisibleEvidenceKind.VISIBLE_EXCERPT,
        content="Nov 24 to Nov 25, 2026",
    )


def _stay_dates_fact() -> SemanticFact:
    return SemanticFact(
        fact_id="fact-1",
        key=SemanticFactKey.STAY_DATES,
        value="Nov 24 to Nov 25, 2026",
        evidence_ids=("visible-1",),
    )


def test_semantic_observation_accepts_only_grounded_positive_facts() -> None:
    observation = SemanticStepObservation(
        step_id=DomStepId.PRICE_CONTEXT_VERIFY,
        observation_id="observation-1",
        facts=(_stay_dates_fact(),),
        visible_evidence=(_visible_excerpt(),),
    )

    assert observation.facts[0].key is SemanticFactKey.STAY_DATES
    assert "absence" not in {key.value for key in SemanticFactKey}
    assert "completeness" not in {key.value for key in SemanticFactKey}
    assert "equivalence" not in {key.value for key in SemanticFactKey}
    assert "eligibility" not in {key.value for key in SemanticFactKey}
    assert "safety" not in {key.value for key in SemanticFactKey}


def test_semantic_observation_rejects_missing_or_stale_grounding() -> None:
    with pytest.raises(ValueError, match="current visible evidence"):
        SemanticStepObservation(
            step_id=DomStepId.PRICE_CONTEXT_VERIFY,
            observation_id="observation-2",
            facts=(_stay_dates_fact(),),
            visible_evidence=(
                VisibleEvidence(
                    evidence_id="different-evidence",
                    kind=VisibleEvidenceKind.ELEMENT_REFERENCE,
                    content="e17",
                ),
            ),
        )


@pytest.mark.parametrize(
    "claim", ["absence", "completeness", "equivalence", "eligibility", "safety"]
)
def test_semantic_fact_rejects_authoritative_claim_keys(claim: str) -> None:
    with pytest.raises(ValueError, match="closed positive vocabulary"):
        SemanticFact(
            fact_id="fact-1",
            key=claim,  # type: ignore[arg-type]
            value="model assertion",
            evidence_ids=("visible-1",),
        )


@pytest.mark.parametrize(
    "value",
    [
        "No reservations found",
        "Inventory is complete",
        "All pages were checked",
        "This room is equivalent and eligible",
        "Booking was cancelled",
    ],
)
def test_semantic_fact_rejects_authoritative_claim_values(value: str) -> None:
    with pytest.raises(ValueError, match="authoritative domain claims"):
        SemanticFact(
            fact_id="fact-1",
            key=SemanticFactKey.INVENTORY_SCOPE,
            value=value,
            evidence_ids=("visible-1",),
        )


@pytest.mark.parametrize(
    "content",
    [
        "https://secure.booking.com/reservation?id=123",
        "authorization: Bearer definitely-not-visible-evidence",
        "password=do-not-keep-this",
    ],
)
def test_visible_evidence_rejects_urls_queries_and_secrets(content: str) -> None:
    with pytest.raises(ValueError, match="cannot contain"):
        VisibleEvidence(
            evidence_id="visible-1",
            kind=VisibleEvidenceKind.VISIBLE_EXCERPT,
            content=content,
        )


def test_only_code_receipt_can_create_verified_step_result() -> None:
    receipt = CodeVerificationReceipt(
        step_id=DomStepId.PRICE_CONTEXT_VERIFY,
        verified_state=PageState.PROPERTY,
        observation_id="observation-1",
        verified_at=NOW,
        verifier="trusted-context-verifier",
    )
    result = StepVerificationResult(
        step_id=DomStepId.PRICE_CONTEXT_VERIFY,
        observation_id="observation-1",
        status=StepVerificationStatus.VERIFIED,
        evidence=frozenset({EvidenceCategory.SUPPORTED_PROPERTY_STRUCTURE}),
        receipt=receipt,
    )

    assert result.receipt is receipt

    with pytest.raises(ValueError, match="require only a code receipt"):
        StepVerificationResult(
            step_id=DomStepId.PRICE_CONTEXT_VERIFY,
            observation_id="observation-1",
            status=StepVerificationStatus.VERIFIED,
            evidence=frozenset(),
            exact_reason=TerminalBrowserReason.PROPERTY_CONTEXT_MISMATCH,
        )


def test_ambiguous_verification_cannot_claim_an_exact_failure() -> None:
    with pytest.raises(ValueError, match="cannot claim an exact reason"):
        StepVerificationResult(
            step_id=DomStepId.PRICE_OFFER_EXTRACTION,
            observation_id="observation-1",
            status=StepVerificationStatus.AMBIGUOUS,
            evidence=frozenset(),
            exact_reason=TerminalBrowserReason.EXPLICIT_UNAVAILABLE,
        )


def test_terminal_diagnosis_is_content_free_and_preserves_model_stop() -> None:
    diagnosis = TerminalBrowserDiagnosis(
        reason=TerminalBrowserReason.PROVIDER_RATE_LIMIT,
        step_id=DomStepId.PRICE_OFFER_EXTRACTION,
        provenance=DiagnosisProvenance.PROVIDER_STOP,
        confidence=1.0,
        evidence=frozenset(),
        operator_action=OperatorAction.RETRY_LATER,
        model_stop_reason=ModelStopReason.PROVIDER_RATE_LIMIT,
    )

    assert diagnosis.model_stop_reason is ModelStopReason.PROVIDER_RATE_LIMIT
    assert not hasattr(diagnosis, "detail")
    assert not hasattr(diagnosis, "url")
    assert not hasattr(diagnosis, "exception")

    check_result = CheckResult.failure(
        booking_id="booking-1",
        checked_at=NOW,
        reason=FailureReason(FailureCode.LLM_ERROR, "provider rate limited"),
        terminal_diagnosis=diagnosis,
    )
    assert check_result.terminal_diagnosis is diagnosis


@pytest.mark.parametrize(
    ("terminal", "failure"),
    [
        (TerminalBrowserReason.PROVIDER_RATE_LIMIT, FailureCode.PROVIDER_RATE_LIMIT),
        (TerminalBrowserReason.DAILY_COST_LIMIT, FailureCode.DAILY_COST_LIMIT),
        (TerminalBrowserReason.TIME_LIMIT, FailureCode.TIME_LIMIT),
        (TerminalBrowserReason.UNRESOLVED_AMBIGUITY, FailureCode.DOM_AMBIGUITY),
        (
            TerminalBrowserReason.CODE_MAINTENANCE_REQUIRED,
            FailureCode.DOM_MAINTENANCE_REQUIRED,
        ),
    ],
)
def test_terminal_reason_maps_to_specific_failure_code(
    terminal: TerminalBrowserReason, failure: FailureCode
) -> None:
    assert failure_code_for_terminal(terminal) is failure


def test_maintenance_diagnosis_requires_model_provenance_and_guidance() -> None:
    with pytest.raises(ValueError, match="only a model diagnosis"):
        TerminalBrowserDiagnosis(
            reason=TerminalBrowserReason.CODE_MAINTENANCE_REQUIRED,
            step_id=DomStepId.INVENTORY_EXTRACTION,
            provenance=DiagnosisProvenance.DETERMINISTIC,
            confidence=1.0,
            evidence=frozenset(),
            operator_action=OperatorAction.MAINTAIN_CODE,
            code_maintenance_required=True,
        )

    diagnosis = TerminalBrowserDiagnosis(
        reason=TerminalBrowserReason.CODE_MAINTENANCE_REQUIRED,
        step_id=DomStepId.INVENTORY_EXTRACTION,
        provenance=DiagnosisProvenance.OPUS_DIAGNOSED,
        confidence=0.88,
        evidence=frozenset({EvidenceCategory.UNSUPPORTED_PAGE_STRUCTURE}),
        operator_action=OperatorAction.MAINTAIN_CODE,
        code_maintenance_required=True,
    )
    assert diagnosis.code_maintenance_required


def test_popup_adoption_result_is_exactly_receipt_or_refusal() -> None:
    receipt = PopupAdoptionReceipt(
        step_id=DomStepId.PRICE_PROPERTY_OPEN,
        observation_id="popup-observation-1",
        page_id="popup-page-1",
        adopted_at=NOW,
    )
    adopted = PopupAdoptionResult(receipt=receipt)
    refused = PopupAdoptionResult(refusal_reason=PopupRefusalReason.MULTIPLE_OPENED)

    assert adopted.is_adopted
    assert not refused.is_adopted

    with pytest.raises(ValueError, match="exactly one"):
        PopupAdoptionResult()
    with pytest.raises(ValueError, match="exactly one"):
        PopupAdoptionResult(
            receipt=receipt,
            refusal_reason=PopupRefusalReason.PROTECTED_DESTINATION,
        )
