from __future__ import annotations

from datetime import UTC, date, datetime

import pytest

from booksaver.application.model_policy import AdaptiveModelSession, BrowserJobCostBudget
from booksaver.domain.agent import LLMUsage
from booksaver.domain.model_policy import (
    AdaptiveModelPortfolio,
    AdaptiveModelRouter,
    AdmissionDecision,
    BrowserJobKind,
    CallerKeyRef,
    CostReconciliation,
    CostReservation,
    EscalationTrigger,
    ModelAttemptOutcome,
    ModelCostEstimator,
    ModelRole,
    ModelStopReason,
    QualificationEvaluator,
    QualificationGate,
    QualificationMetrics,
    ReservationStatus,
    TokenEnvelope,
    UsdAmount,
)


class _Ledger:
    def __init__(self) -> None:
        self.requests = []
        self.reconciliations = []

    def reserve_call(self, request):
        self.requests.append(request)
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
            request.reservation_id,
            request.charged_cost,
            ReservationStatus.CONSERVATIVE
            if request.conservative
            else ReservationStatus.CHARGED,
        )

    def list_attempts(self, job_id):
        return ()


def _budget(ledger: _Ledger) -> BrowserJobCostBudget:
    return BrowserJobCostBudget(
        job_id="job-1",
        job_kind=BrowserJobKind.CHECK_NOW,
        caller_key_ref=CallerKeyRef(1, "personal", "encrypted_user_key"),
        ledger=ledger,
        estimator=ModelCostEstimator(),
        clock=lambda: datetime(2026, 8, 13, tzinfo=UTC),
    )


def test_fixed_portfolio_is_sonnet_then_opus_and_rejects_fable() -> None:
    portfolio = AdaptiveModelPortfolio()
    assert portfolio.primary(ModelRole.RECOVERY, "p-v1").model_id == "claude-sonnet-5"
    assert portfolio.escalation(ModelRole.RECOVERY, "p-v1").model_id == "claude-opus-5"

    with pytest.raises(ValueError, match="Sonnet 5"):
        AdaptiveModelPortfolio(primary_model="claude-fable-5")
    with pytest.raises(ValueError, match="Opus 5"):
        AdaptiveModelPortfolio(escalation_model="claude-fable-5")


def test_conclusive_deterministic_failure_produces_no_attempt() -> None:
    router = AdaptiveModelRouter(AdaptiveModelPortfolio())
    decision = router.initial(
        role=ModelRole.CLASSIFICATION,
        prompt_version="page-state-v1",
        deterministic_stop=ModelStopReason.AUTHENTICATION_REQUIRED,
    )
    assert decision.plan is None
    assert decision.stop_reason is ModelStopReason.AUTHENTICATION_REQUIRED

    # The convenience API needs no budget/ledger at all for predictable stops.
    exact = AdaptiveModelSession.deterministic_stop(ModelStopReason.CAPTCHA)
    assert exact.stop_reason is ModelStopReason.CAPTCHA

    ledger = _Ledger()
    AdaptiveModelSession.deterministic_stop(ModelStopReason.AUTHENTICATION_REQUIRED)
    assert ledger.requests == []
    assert ledger.reconciliations == []


@pytest.mark.parametrize(
    "trigger",
    [
        EscalationTrigger.SEMANTIC_NO_PROGRESS,
        EscalationTrigger.REPEATED_INVALID_SCHEMA,
        EscalationTrigger.UNSAFE_PROPOSAL_REJECTED,
        EscalationTrigger.UNRESOLVED_LOW_CONFIDENCE,
        EscalationTrigger.UNVERIFIED_SONNET_EXHAUSTION,
    ],
)
def test_measured_quality_failure_escalates_once_to_opus(trigger) -> None:
    ledger = _Ledger()
    session = AdaptiveModelSession(
        role=ModelRole.RECOVERY,
        prompt_version="recovery-v1",
        budget=_budget(ledger),
    )
    first = session.start(TokenEnvelope(1_000, 100))
    second = session.escalate(trigger, TokenEnvelope(1_000, 100))

    assert first.attempt is not None
    assert first.attempt.plan.profile.model_id == "claude-sonnet-5"
    assert second.attempt is not None
    assert second.attempt.plan.profile.model_id == "claude-opus-5"
    assert [request.attempt_ordinal for request in ledger.requests] == [1, 2]


def test_terminal_after_sonnet_does_not_reserve_opus() -> None:
    ledger = _Ledger()
    session = AdaptiveModelSession(
        role=ModelRole.RECOVERY,
        prompt_version="recovery-v1",
        budget=_budget(ledger),
    )
    session.start(TokenEnvelope(1_000, 100))
    terminal = session.escalate(
        EscalationTrigger.SEMANTIC_NO_PROGRESS,
        TokenEnvelope(1_000, 100),
        terminal_stop=ModelStopReason.AUTHENTICATION_REQUIRED,
    )
    assert terminal.stop_reason is ModelStopReason.AUTHENTICATION_REQUIRED
    assert len(ledger.requests) == 1


def test_two_sessions_share_job_global_attempt_order() -> None:
    ledger = _Ledger()
    budget = _budget(ledger)
    recovery = AdaptiveModelSession(
        role=ModelRole.RECOVERY,
        prompt_version="recovery-v1",
        budget=budget,
    )
    interpretation = AdaptiveModelSession(
        role=ModelRole.INTERPRETATION,
        prompt_version="inventory-v1",
        budget=budget,
    )

    first = recovery.start(TokenEnvelope(1_000, 100))
    second = interpretation.start(TokenEnvelope(1_000, 100))
    third = recovery.escalate(
        EscalationTrigger.SEMANTIC_NO_PROGRESS, TokenEnvelope(1_000, 100)
    )

    assert first.attempt is not None
    assert second.attempt is not None
    assert third.attempt is not None
    assert [request.attempt_ordinal for request in ledger.requests] == [1, 2, 3]
    assert [
        first.attempt.plan.ordinal,
        second.attempt.plan.ordinal,
        third.attempt.plan.ordinal,
    ] == [1, 2, 3]


def test_cost_estimation_and_reconciliation_use_exact_microdollars() -> None:
    portfolio = AdaptiveModelPortfolio()
    profile = portfolio.primary(ModelRole.EXTRACTION, "extract-v1")
    estimator = ModelCostEstimator()
    assert estimator.estimate(profile, TokenEnvelope(1_000, 100)) == UsdAmount(3_000)
    assert estimator.charge(profile, LLMUsage(800, 50)) == UsdAmount(2_100)

    ledger = _Ledger()
    budget = _budget(ledger)
    session = AdaptiveModelSession(
        role=ModelRole.EXTRACTION,
        prompt_version="extract-v1",
        budget=budget,
    )
    admitted = session.start(TokenEnvelope(1_000, 100))
    assert admitted.attempt is not None
    result = budget.reconcile(
        admitted.attempt,
        usage=LLMUsage(800, 50),
        latency_ms=50,
        outcome=ModelAttemptOutcome.RECOVERED,
    )
    assert result.charged_cost == UsdAmount(2_100)


def test_sonnet_pricing_changes_on_the_published_utc_boundary() -> None:
    profile = AdaptiveModelPortfolio().primary(ModelRole.RECOVERY, "prompt-v1")
    estimator = ModelCostEstimator()

    assert estimator.estimate(
        profile,
        TokenEnvelope(1_000, 100),
        utc_date=date(2026, 8, 31),
    ) == UsdAmount(3_000)
    assert estimator.estimate(
        profile,
        TokenEnvelope(1_000, 100),
        utc_date=date(2026, 9, 1),
    ) == UsdAmount(4_500)


def _metrics(correct: int, prohibited: int = 0) -> QualificationMetrics:
    return QualificationMetrics(
        runs=10,
        correct_runs=correct,
        diagnosis_runs=10,
        diagnosis_correct_runs=correct,
        schema_valid_runs=10,
        prohibited_action_proposals=0,
        prohibited_action_executions=prohibited,
        escalation_count=2,
        total_calls=12,
        total_actions=3,
        input_tokens=1_000,
        output_tokens=100,
        latency_ms=500,
        estimated_cost=UsdAmount(3_000),
    )


def test_qualification_requires_nine_of_ten_and_zero_prohibited_execution() -> None:
    evaluator = QualificationEvaluator()
    passed = evaluator.evaluate(
        profile_identity="anthropic:portfolio-v1",
        fixture_version="corpus-v1",
        metrics=_metrics(9),
        created_at=datetime.now(UTC),
    )
    wrong = evaluator.evaluate(
        profile_identity="anthropic:portfolio-v1",
        fixture_version="corpus-v1",
        metrics=_metrics(8),
        created_at=datetime.now(UTC),
    )
    unsafe = evaluator.evaluate(
        profile_identity="anthropic:portfolio-v1",
        fixture_version="corpus-v1",
        metrics=_metrics(10, prohibited=1),
        created_at=datetime.now(UTC),
    )
    assert passed.gate is QualificationGate.PASSED
    assert wrong.gate is QualificationGate.FAILED
    assert unsafe.gate is QualificationGate.FAILED
