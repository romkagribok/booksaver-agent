"""Application services for adaptive model routing and dollar admission."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from threading import Lock
from typing import Protocol

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
    ModelAttemptAudit,
    ModelAttemptOutcome,
    ModelAttemptPlan,
    ModelCostEstimator,
    ModelRole,
    ModelRoutingDecision,
    ModelStopReason,
    ModelTier,
    ReconciliationRequest,
    ReservationRequest,
    TokenEnvelope,
    UsdAmount,
)


class SpendLedger(Protocol):
    def reserve_call(self, request: ReservationRequest) -> AdmissionDecision: ...

    def reconcile_call(
        self, request: ReconciliationRequest
    ) -> CostReconciliation: ...

    def list_attempts(self, job_id: str) -> tuple[ModelAttemptAudit, ...]: ...


class AdaptiveModelStopped(RuntimeError):
    """An exact content-free terminal produced before or after a provider call."""

    def __init__(self, reason: ModelStopReason) -> None:
        super().__init__(reason.value)
        self.reason = reason


@dataclass(frozen=True, slots=True)
class AdmittedModelAttempt:
    plan: ModelAttemptPlan
    reservation: CostReservation
    caller_key_ref: CallerKeyRef


@dataclass(frozen=True, slots=True)
class AttemptAdmission:
    attempt: AdmittedModelAttempt | None = None
    stop_reason: ModelStopReason | None = None

    def __post_init__(self) -> None:
        if (self.attempt is None) == (self.stop_reason is None):
            raise ValueError("attempt admission requires exactly one attempt or stop reason")


class BrowserJobCostBudget:
    """Lazy budget shared by every LLM role in one coordinator admission.

    Construction performs no persistence or key resolution.  A row is created
    only when an ambiguous episode asks to admit a concrete provider call.
    """

    def __init__(
        self,
        *,
        job_id: str,
        job_kind: BrowserJobKind,
        caller_key_ref: CallerKeyRef,
        ledger: SpendLedger,
        estimator: ModelCostEstimator,
        job_limit: UsdAmount = UsdAmount(1_000_000),
        day_limit: UsdAmount = UsdAmount(10_000_000),
        opus_diagnostic_envelope: TokenEnvelope = TokenEnvelope(30_000, 1_024),
        preserve_opus_diagnostic: bool = True,
        initial_attempt_ordinal: int = 1,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        if not job_id:
            raise ValueError("job_id is required")
        if isinstance(initial_attempt_ordinal, bool) or initial_attempt_ordinal < 1:
            raise ValueError("initial_attempt_ordinal must be positive")
        self.job_id = job_id
        self.job_kind = job_kind
        self.caller_key_ref = caller_key_ref
        self._ledger = ledger
        self._estimator = estimator
        self._job_limit = job_limit
        self._day_limit = day_limit
        self._opus_diagnostic_envelope = opus_diagnostic_envelope
        self._preserve_opus_diagnostic = preserve_opus_diagnostic
        self._clock = clock
        self._ordinal_lock = Lock()
        self._next_attempt_ordinal = initial_attempt_ordinal

    def admit(self, plan: ModelAttemptPlan, envelope: TokenEnvelope) -> AttemptAdmission:
        now = self._clock()
        if now.tzinfo is None:
            raise ValueError("budget clock must return a timezone-aware datetime")
        utc_date = now.astimezone(UTC).date()
        reserved = self._estimator.estimate(
            plan.profile,
            envelope,
            utc_date=utc_date,
        )
        preserve = UsdAmount()
        if plan.profile.tier is ModelTier.SONNET and self._preserve_opus_diagnostic:
            portfolio = AdaptiveModelPortfolio()
            diagnostic = portfolio.escalation(
                ModelRole.DIAGNOSTIC, "booking-browser-diagnostic-v1"
            )
            preserve = self._estimator.estimate(
                diagnostic,
                self._opus_diagnostic_envelope,
                utc_date=utc_date,
            )
        reservation_id = f"llm-{uuid.uuid4().hex}"
        with self._ordinal_lock:
            job_plan = replace(plan, ordinal=self._next_attempt_ordinal)
            decision = self._ledger.reserve_call(
                ReservationRequest(
                    reservation_id=reservation_id,
                    job_id=self.job_id,
                    job_kind=self.job_kind,
                    caller_user_id=self.caller_key_ref.caller_user_id,
                    utc_date=utc_date,
                    attempt_ordinal=job_plan.ordinal,
                    profile=job_plan.profile,
                    trigger=job_plan.trigger,
                    reserved_cost=reserved,
                    job_limit=self._job_limit,
                    day_limit=self._day_limit,
                    preserved_job_allowance=preserve,
                    price_table_version=self._estimator.version,
                    created_at=now,
                )
            )
            if decision.reservation is not None:
                self._next_attempt_ordinal += 1
        if decision.denied_reason is not None:
            return AttemptAdmission(stop_reason=decision.denied_reason)
        assert decision.reservation is not None
        return AttemptAdmission(
            attempt=AdmittedModelAttempt(
                plan=job_plan,
                reservation=decision.reservation,
                caller_key_ref=self.caller_key_ref,
            )
        )

    def reconcile(
        self,
        attempt: AdmittedModelAttempt,
        *,
        usage: LLMUsage | None,
        latency_ms: int,
        outcome: ModelAttemptOutcome,
        cache_read_input_tokens: int = 0,
        cache_creation_input_tokens: int = 0,
    ) -> CostReconciliation:
        if usage is None and (cache_read_input_tokens or cache_creation_input_tokens):
            raise ValueError("prompt-cache usage requires completed token usage")
        charged = (
            attempt.reservation.reserved_cost
            if usage is None
            else self._estimator.charge_anthropic_prompt_cache(
                attempt.plan.profile,
                usage,
                cache_read_input_tokens=cache_read_input_tokens,
                cache_creation_input_tokens=cache_creation_input_tokens,
                utc_date=attempt.reservation.utc_date,
            )
            if cache_read_input_tokens or cache_creation_input_tokens
            else self._estimator.charge(
                attempt.plan.profile,
                usage,
                utc_date=attempt.reservation.utc_date,
            )
        )
        return self._ledger.reconcile_call(
            ReconciliationRequest(
                reservation_id=attempt.reservation.reservation_id,
                charged_cost=charged,
                usage=usage,
                latency_ms=latency_ms,
                outcome=outcome,
                conservative=usage is None,
                completed_at=self._clock(),
            )
        )

    def ordered_attempts(self) -> tuple[ModelAttemptAudit, ...]:
        return self._ledger.list_attempts(self.job_id)


class AdaptiveModelSession:
    """State machine for one explicitly ambiguous model-assisted episode."""

    def __init__(
        self,
        *,
        role: ModelRole,
        prompt_version: str,
        budget: BrowserJobCostBudget,
        portfolio: AdaptiveModelPortfolio | None = None,
    ) -> None:
        self._role = role
        self._prompt_version = prompt_version
        self._budget = budget
        self._router = AdaptiveModelRouter(portfolio or AdaptiveModelPortfolio())
        self._primary_started = False
        self._opus_started = False
        self._terminal: ModelStopReason | None = None

    @classmethod
    def deterministic_stop(
        cls, reason: ModelStopReason
    ) -> ModelRoutingDecision:
        """Return an exact known result without constructing a session or ledger call."""
        return ModelRoutingDecision(stop_reason=reason)

    def start(self, envelope: TokenEnvelope) -> AttemptAdmission:
        if self._primary_started or self._terminal is not None:
            raise RuntimeError("adaptive model session has already started")
        decision = self._router.initial(
            role=self._role, prompt_version=self._prompt_version
        )
        assert decision.plan is not None
        admitted = self._budget.admit(decision.plan, envelope)
        if admitted.attempt is not None:
            self._primary_started = True
        else:
            self._terminal = admitted.stop_reason
        return admitted

    def escalate(
        self,
        trigger: EscalationTrigger,
        envelope: TokenEnvelope,
        *,
        terminal_stop: ModelStopReason | None = None,
    ) -> AttemptAdmission:
        if not self._primary_started:
            raise RuntimeError("Sonnet must be attempted before Opus")
        if self._opus_started or self._terminal is not None:
            raise RuntimeError("adaptive model session is already terminal")
        decision = self._router.after_sonnet(
            role=self._role,
            prompt_version=self._prompt_version,
            trigger=trigger,
            terminal_stop=terminal_stop,
        )
        if decision.stop_reason is not None:
            self._terminal = decision.stop_reason
            return AttemptAdmission(stop_reason=decision.stop_reason)
        assert decision.plan is not None
        admitted = self._budget.admit(decision.plan, envelope)
        if admitted.attempt is not None:
            self._opus_started = True
        else:
            self._terminal = admitted.stop_reason
        return admitted

    def continue_primary(self, envelope: TokenEnvelope) -> AttemptAdmission:
        """Admit another ordinary Sonnet turn in the same ambiguous episode.

        ``AgentBrain`` is a multi-turn port: each ``decide`` invocation is one
        physical provider call.  Those ordinary turns share the same session
        and job budget until code-owned quality evidence requests the single
        Opus escalation.
        """
        if not self._primary_started:
            raise RuntimeError("Sonnet must be attempted before it can continue")
        if self._opus_started or self._terminal is not None:
            raise RuntimeError("adaptive model session is already terminal")
        decision = self._router.initial(
            role=self._role,
            prompt_version=self._prompt_version,
        )
        assert decision.plan is not None
        admitted = self._budget.admit(decision.plan, envelope)
        if admitted.attempt is None:
            self._terminal = admitted.stop_reason
        return admitted

    def stop(self, reason: ModelStopReason) -> None:
        self._terminal = reason
