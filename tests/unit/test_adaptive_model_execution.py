from __future__ import annotations

from datetime import UTC, datetime

import pytest

from booksaver.application.model_policy import BrowserJobCostBudget
from booksaver.domain.agent import LLMUsage
from booksaver.domain.model_policy import (
    AdmissionDecision,
    BrowserJobKind,
    CallerKeyRef,
    CostReconciliation,
    CostReservation,
    EscalationTrigger,
    ModelCostEstimator,
    ModelRole,
    ModelStopReason,
    ReservationStatus,
    TokenEnvelope,
)
from booksaver.infrastructure.llm.adaptive_execution import (
    AdaptiveModelStopped,
    AdaptiveRoleExecutor,
)
from booksaver.infrastructure.llm.anthropic_adapter import (
    LLMFailureKind,
    LLMProviderError,
)


class _Ledger:
    def __init__(self, *, was_new: bool = True) -> None:
        self.was_new = was_new
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
                was_new=self.was_new,
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


class _Delegate:
    def __init__(self, model: str, calls: list[str]) -> None:
        self.model = model
        self.calls = calls
        self.last_usage: LLMUsage | None = None

    def call(self, failure: LLMFailureKind | None = None) -> str:
        self.calls.append(self.model)
        self.last_usage = LLMUsage(100, 10)
        if failure is not None:
            raise LLMProviderError("safe failure", kind=failure)
        return self.model


def _executor(
    ledger: _Ledger,
    calls: list[str],
) -> AdaptiveRoleExecutor[_Delegate]:
    budget = BrowserJobCostBudget(
        job_id="job-runtime",
        job_kind=BrowserJobKind.CHECK_NOW,
        caller_key_ref=CallerKeyRef(1, "personal", "encrypted_user_key"),
        ledger=ledger,
        estimator=ModelCostEstimator(),
        clock=lambda: datetime(2026, 8, 13, tzinfo=UTC),
    )
    return AdaptiveRoleExecutor(
        role=ModelRole.RECOVERY,
        prompt_version="runtime-test-v1",
        budget=budget,
        delegate_factory=lambda profile: _Delegate(profile.model_id, calls),
        envelope=TokenEnvelope(1_000, 100),
        monotonic=iter((1.0, 1.1, 2.0, 2.2, 3.0, 3.3)).__next__,
    )


def test_multi_turn_sonnet_then_one_opus_reserves_and_reconciles_each_call() -> None:
    ledger = _Ledger()
    calls: list[str] = []
    executor = _executor(ledger, calls)

    assert executor.invoke_primary(lambda delegate: delegate.call()) == "claude-sonnet-5"
    assert executor.invoke_primary(lambda delegate: delegate.call()) == "claude-sonnet-5"
    assert (
        executor.invoke_escalation(
            EscalationTrigger.SEMANTIC_NO_PROGRESS,
            lambda delegate: delegate.call(),
        )
        == "claude-opus-5"
    )

    assert calls == ["claude-sonnet-5", "claude-sonnet-5", "claude-opus-5"]
    assert [request.attempt_ordinal for request in ledger.requests] == [1, 2, 3]
    assert [request.profile.model_id for request in ledger.requests] == calls
    assert ledger.requests[0].preserved_job_allowance.micro_usd > 0
    assert ledger.requests[1].preserved_job_allowance.micro_usd > 0
    assert ledger.requests[2].preserved_job_allowance.micro_usd == 0
    assert len(ledger.reconciliations) == 3

    with pytest.raises(RuntimeError, match="already terminal"):
        executor.invoke_escalation(
            EscalationTrigger.UNVERIFIED_SONNET_EXHAUSTION,
            lambda delegate: delegate.call(),
        )


def test_repeated_invalid_sonnet_responses_are_reconciled_then_retried_on_opus() -> None:
    ledger = _Ledger()
    calls: list[str] = []
    executor = _executor(ledger, calls)

    result = executor.invoke_primary(
        lambda delegate: delegate.call(
            LLMFailureKind.INVALID_RESPONSE
            if delegate.model == "claude-sonnet-5"
            else None
        )
    )

    assert result == "claude-opus-5"
    assert calls == ["claude-sonnet-5", "claude-sonnet-5", "claude-opus-5"]
    assert [item.outcome.value for item in ledger.reconciliations] == [
        "quality_failed",
        "quality_failed",
        "completed",
    ]


def test_returned_model_value_is_completed_not_semantically_recovered() -> None:
    ledger = _Ledger()
    calls: list[str] = []
    executor = _executor(ledger, calls)

    assert executor.invoke_primary(lambda delegate: delegate.call()) == "claude-sonnet-5"

    assert ledger.reconciliations[0].outcome.value == "completed"


@pytest.mark.parametrize(
    ("failure", "stop"),
    [
        (LLMFailureKind.AUTHENTICATION, ModelStopReason.PROVIDER_AUTHENTICATION),
        (LLMFailureKind.RATE_LIMIT, ModelStopReason.PROVIDER_RATE_LIMIT),
        (LLMFailureKind.UNAVAILABLE, ModelStopReason.PROVIDER_UNAVAILABLE),
        (LLMFailureKind.TRANSPORT, ModelStopReason.PROVIDER_UNAVAILABLE),
    ],
)
def test_exact_provider_terminal_does_not_spend_opus(
    failure: LLMFailureKind,
    stop: ModelStopReason,
) -> None:
    ledger = _Ledger()
    calls: list[str] = []
    executor = _executor(ledger, calls)

    with pytest.raises(AdaptiveModelStopped) as raised:
        executor.invoke_primary(lambda delegate: delegate.call(failure))

    assert raised.value.reason is stop
    assert calls == ["claude-sonnet-5"]
    assert len(ledger.requests) == 1
    assert len(ledger.reconciliations) == 1


def test_replayed_reservation_never_invokes_or_reconciles_provider() -> None:
    ledger = _Ledger(was_new=False)
    calls: list[str] = []
    executor = _executor(ledger, calls)

    with pytest.raises(AdaptiveModelStopped) as raised:
        executor.invoke_primary(lambda delegate: delegate.call())

    assert raised.value.reason is ModelStopReason.COST_ACCOUNTING_ERROR
    assert calls == []
    assert ledger.reconciliations == []


def test_delegate_construction_failure_conservatively_reconciles_reservation() -> None:
    ledger = _Ledger()
    budget = BrowserJobCostBudget(
        job_id="job-construction-failure",
        job_kind=BrowserJobKind.CHECK_NOW,
        caller_key_ref=CallerKeyRef(1, "personal", "encrypted_user_key"),
        ledger=ledger,
        estimator=ModelCostEstimator(),
        clock=lambda: datetime(2026, 8, 13, tzinfo=UTC),
    )
    executor = AdaptiveRoleExecutor(
        role=ModelRole.RECOVERY,
        prompt_version="runtime-test-v1",
        budget=budget,
        delegate_factory=lambda profile: (_ for _ in ()).throw(ImportError("anthropic")),
        envelope=TokenEnvelope(1_000, 100),
        monotonic=iter((1.0, 1.1)).__next__,
    )

    with pytest.raises(ImportError, match="anthropic"):
        executor.invoke_primary(lambda delegate: delegate.call())

    assert len(ledger.requests) == 1
    assert len(ledger.reconciliations) == 1
    reconciled = ledger.reconciliations[0]
    assert reconciled.usage is None
    assert reconciled.conservative
    assert reconciled.outcome.value == "provider_failed"
    assert reconciled.charged_cost == ledger.requests[0].reserved_cost
