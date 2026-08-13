"""Caller-bound, spend-admitted execution for approved adaptive model roles.

The browser workflows decide *when* page state is ambiguous and whether a
valid model result made semantic progress.  This module owns the narrower
provider boundary: reserve before every physical call, use the profile selected
by the policy, reconcile exactly once, and never call again for an idempotently
replayed reservation.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import replace
from typing import TYPE_CHECKING, Generic, Protocol, TypeVar, cast

from booksaver.application.model_policy import (
    AdaptiveModelSession,
    AdaptiveModelStopped,
    AdmittedModelAttempt,
    AttemptAdmission,
    BrowserJobCostBudget,
)
from booksaver.application.ports import (
    AgentBrain,
    ExtractionResult,
    InventoryInterpreter,
    LLMExtractor,
)
from booksaver.domain.account_sync import ReservationObservation
from booksaver.domain.agent import AgentAction, AgentTurnContext, LLMUsage
from booksaver.domain.model_policy import (
    CallerKeyRef,
    EscalationTrigger,
    ModelAttemptOutcome,
    ModelProfile,
    ModelRole,
    ModelStopReason,
    TokenEnvelope,
)
from booksaver.domain.models import Booking
from booksaver.domain.offer import OfferCandidate

from .anthropic_adapter import LLMFailureKind, LLMProviderError

if TYPE_CHECKING:
    from booksaver.application.browser_resilience import ModelPageStateClassifier
    from booksaver.application.ports import RegisteredPageStateResolver

_AGENT_ENVELOPE = TokenEnvelope(50_000, 1_024)
_STRUCTURED_ENVELOPE = TokenEnvelope(20_000, 2_048)

TDelegate = TypeVar("TDelegate")
TResult = TypeVar("TResult")


class _UsageBearing(Protocol):
    last_usage: LLMUsage | None


class CallerBoundDelegateFactory(Protocol):
    @property
    def key_ref(self) -> CallerKeyRef: ...

    def agent_brain(self, profile: ModelProfile) -> AgentBrain: ...
    def inventory_interpreter(self, profile: ModelProfile) -> InventoryInterpreter: ...
    def extractor(self, profile: ModelProfile) -> LLMExtractor: ...
    def page_classifier(self, profile: ModelProfile) -> ModelPageStateClassifier: ...


def _provider_stop(kind: LLMFailureKind) -> ModelStopReason:
    return {
        LLMFailureKind.INVALID_RESPONSE: ModelStopReason.INVALID_PROVIDER_RESPONSE,
        LLMFailureKind.AUTHENTICATION: ModelStopReason.PROVIDER_AUTHENTICATION,
        LLMFailureKind.RATE_LIMIT: ModelStopReason.PROVIDER_RATE_LIMIT,
        LLMFailureKind.UNAVAILABLE: ModelStopReason.PROVIDER_UNAVAILABLE,
        LLMFailureKind.TRANSPORT: ModelStopReason.PROVIDER_UNAVAILABLE,
    }[kind]


class AdaptiveRoleExecutor(Generic[TDelegate]):
    """Execute one model role through a single Sonnet-to-Opus session."""

    def __init__(
        self,
        *,
        role: ModelRole,
        prompt_version: str,
        budget: BrowserJobCostBudget,
        delegate_factory: Callable[[ModelProfile], TDelegate],
        envelope: TokenEnvelope,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        self._budget = budget
        self._delegate_factory = delegate_factory
        self._envelope = envelope
        self._monotonic = monotonic
        self._session = AdaptiveModelSession(
            role=role,
            prompt_version=prompt_version,
            budget=budget,
        )
        self._primary_calls = 0
        self._consecutive_invalid_responses = 0
        self._delegates: dict[str, TDelegate] = {}
        self.last_usage: LLMUsage | None = None
        self.last_profile: ModelProfile | None = None
        self.last_failure_kind: LLMFailureKind | None = None
        self.last_stop_reason: ModelStopReason | None = None

    def invoke_primary(self, operation: Callable[[TDelegate], TResult]) -> TResult:
        """Invoke Sonnet, escalating only after repeated invalid responses."""
        admission = (
            self._session.start(self._envelope)
            if self._primary_calls == 0
            else self._session.continue_primary(self._envelope)
        )
        self._primary_calls += 1
        try:
            result = self._invoke_admitted(admission, operation)
            self._consecutive_invalid_responses = 0
            return result
        except LLMProviderError as exc:
            if exc.kind is LLMFailureKind.INVALID_RESPONSE:
                self._consecutive_invalid_responses += 1
                if self._consecutive_invalid_responses < 2:
                    return self.invoke_primary(operation)
                return self.invoke_escalation(
                    EscalationTrigger.REPEATED_INVALID_SCHEMA,
                    operation,
                )
            reason = _provider_stop(exc.kind)
            self.last_stop_reason = reason
            raise AdaptiveModelStopped(reason) from None

    def invoke_escalation(
        self,
        trigger: EscalationTrigger,
        operation: Callable[[TDelegate], TResult],
    ) -> TResult:
        """Invoke the sole Opus turn after caller-supplied typed quality evidence."""
        admission = self._session.escalate(trigger, self._envelope)
        try:
            return self._invoke_admitted(admission, operation)
        except LLMProviderError as exc:
            reason = _provider_stop(exc.kind)
            self.last_stop_reason = reason
            raise AdaptiveModelStopped(reason) from None

    def _invoke_admitted(
        self,
        admission: AttemptAdmission,
        operation: Callable[[TDelegate], TResult],
    ) -> TResult:
        if admission.stop_reason is not None:
            self.last_stop_reason = admission.stop_reason
            raise AdaptiveModelStopped(admission.stop_reason)
        assert admission.attempt is not None
        attempt = admission.attempt
        if not attempt.reservation.was_new:
            # The ledger has seen this reservation already.  Its original call
            # may have completed or may still be in flight; either way another
            # physical provider invocation would violate idempotency.
            self.last_stop_reason = ModelStopReason.COST_ACCOUNTING_ERROR
            raise AdaptiveModelStopped(ModelStopReason.COST_ACCOUNTING_ERROR)

        self.last_usage = None
        self.last_profile = attempt.plan.profile
        self.last_failure_kind = None
        started = self._monotonic()
        delegate: TDelegate | None = None
        # A returned action/value is still untrusted and not semantic proof that
        # the browser postcondition was recovered.  The workflow owns that
        # later verification; cost audit records only physical-call completion.
        outcome = ModelAttemptOutcome.COMPLETED
        try:
            delegate = self._delegate_for(attempt)
            return operation(delegate)
        except LLMProviderError as exc:
            self.last_failure_kind = exc.kind
            outcome = (
                ModelAttemptOutcome.QUALITY_FAILED
                if exc.kind is LLMFailureKind.INVALID_RESPONSE
                else ModelAttemptOutcome.PROVIDER_FAILED
            )
            raise
        except Exception:
            outcome = ModelAttemptOutcome.PROVIDER_FAILED
            raise
        finally:
            usage = (
                getattr(cast(_UsageBearing, delegate), "last_usage", None)
                if delegate is not None
                else None
            )
            self.last_usage = usage if isinstance(usage, LLMUsage) else None
            elapsed_ms = max(0, int((self._monotonic() - started) * 1_000))
            self._budget.reconcile(
                attempt,
                usage=self.last_usage,
                latency_ms=elapsed_ms,
                outcome=outcome,
            )

    def _delegate_for(self, attempt: AdmittedModelAttempt) -> TDelegate:
        identity = attempt.plan.profile.identity
        delegate = self._delegates.get(identity)
        if delegate is None:
            delegate = self._delegate_factory(attempt.plan.profile)
            self._delegates[identity] = delegate
        return delegate


class AdaptiveAgentBrain:
    """Multi-turn ``AgentBrain`` whose every decision is individually admitted."""

    provider = "anthropic"
    role = "navigation_agent"

    def __init__(self, executor: AdaptiveRoleExecutor[AgentBrain], prompt_version: str) -> None:
        self._executor = executor
        self.prompt_version = prompt_version

    @property
    def model(self) -> str:
        profile = self._executor.last_profile
        return profile.model_id if profile is not None else "claude-sonnet-5"

    @property
    def last_usage(self) -> LLMUsage | None:
        return self._executor.last_usage

    @property
    def last_profile(self) -> ModelProfile | None:
        """Exact admitted profile used by the latest physical call."""

        return self._executor.last_profile

    def decide(self, context: AgentTurnContext) -> AgentAction:
        return self._executor.invoke_primary(lambda brain: brain.decide(context))

    def decide_with_escalation(
        self,
        context: AgentTurnContext,
        trigger: EscalationTrigger,
    ) -> AgentAction:
        return self._executor.invoke_escalation(
            trigger,
            lambda brain: brain.decide(
                replace(context, terminal_diagnosis_required=True)
            ),
        )


class AdaptiveInventoryInterpreter:
    def __init__(self, executor: AdaptiveRoleExecutor[InventoryInterpreter]) -> None:
        self._executor = executor

    @property
    def last_usage(self) -> LLMUsage | None:
        return self._executor.last_usage

    @property
    def last_profile(self) -> ModelProfile | None:
        return self._executor.last_profile

    def interpret(
        self,
        page_text: str,
        source_url: str,
    ) -> tuple[ReservationObservation, ...]:
        return self._executor.invoke_primary(
            lambda interpreter: interpreter.interpret(page_text, source_url)
        )

    def interpret_with_escalation(
        self,
        page_text: str,
        source_url: str,
        trigger: EscalationTrigger,
    ) -> tuple[ReservationObservation, ...]:
        return self._executor.invoke_escalation(
            trigger,
            lambda interpreter: interpreter.interpret(page_text, source_url),
        )


class AdaptiveExtractor:
    def __init__(self, executor: AdaptiveRoleExecutor[LLMExtractor]) -> None:
        self._executor = executor

    @property
    def last_usage(self) -> LLMUsage | None:
        return self._executor.last_usage

    @property
    def last_profile(self) -> ModelProfile | None:
        """Return the profile used by the most recent physical extraction call."""

        return self._executor.last_profile

    def extract_price(self, page_text: str, booking: Booking) -> ExtractionResult:
        return self._executor.invoke_primary(
            lambda extractor: extractor.extract_price(page_text, booking)
        )

    def extract_offers(self, page_text: str, booking: Booking) -> list[OfferCandidate]:
        return self._executor.invoke_primary(
            lambda extractor: extractor.extract_offers(page_text, booking)
        )

    def extract_offers_with_escalation(
        self,
        page_text: str,
        booking: Booking,
        trigger: EscalationTrigger,
    ) -> list[OfferCandidate]:
        return self._executor.invoke_escalation(
            trigger,
            lambda extractor: extractor.extract_offers(page_text, booking),
        )


class AdaptiveAnthropicRuntimeFactory:
    """Build all approved roles against one caller key and browser-job budget."""

    def __init__(
        self,
        *,
        delegates: CallerBoundDelegateFactory,
        budget: BrowserJobCostBudget,
    ) -> None:
        if delegates.key_ref != budget.caller_key_ref:
            raise ValueError("adaptive budget and model delegates must use the same caller key")
        self._delegates = delegates
        self._budget = budget

    @property
    def delegates(self) -> CallerBoundDelegateFactory:
        """Expose the already caller-bound factory to lazy role adapters."""

        return self._delegates

    def agent_brain(
        self,
        *,
        prompt_version: str = "booking-browser-recovery-v3",
        envelope: TokenEnvelope = _AGENT_ENVELOPE,
    ) -> AdaptiveAgentBrain:
        executor = self.role_executor(
            role=ModelRole.RECOVERY,
            prompt_version=prompt_version,
            envelope=envelope,
            delegate_factory=self._delegates.agent_brain,
        )
        return AdaptiveAgentBrain(executor, prompt_version)

    def inventory_interpreter(
        self,
        *,
        prompt_version: str = "booking-inventory-interpretation-v1",
        envelope: TokenEnvelope = _STRUCTURED_ENVELOPE,
    ) -> AdaptiveInventoryInterpreter:
        executor = self.role_executor(
            role=ModelRole.INTERPRETATION,
            prompt_version=prompt_version,
            envelope=envelope,
            delegate_factory=self._delegates.inventory_interpreter,
        )
        return AdaptiveInventoryInterpreter(executor)

    def extractor(
        self,
        *,
        prompt_version: str = "booking-offer-extraction-v1",
        envelope: TokenEnvelope = _STRUCTURED_ENVELOPE,
    ) -> AdaptiveExtractor:
        executor = self.role_executor(
            role=ModelRole.EXTRACTION,
            prompt_version=prompt_version,
            envelope=envelope,
            delegate_factory=self._delegates.extractor,
        )
        return AdaptiveExtractor(executor)

    def page_state_resolver(self) -> RegisteredPageStateResolver:
        from booksaver.infrastructure.llm.page_state_classifier import (
            CallerBoundPageStateResolver,
        )

        return CallerBoundPageStateResolver(
            factory=self._delegates,
            budget=self._budget,
        )

    def role_executor(
        self,
        *,
        role: ModelRole,
        prompt_version: str,
        envelope: TokenEnvelope,
        delegate_factory: Callable[[ModelProfile], TDelegate],
    ) -> AdaptiveRoleExecutor[TDelegate]:
        """Build classifier/diagnostic or future role adapters without a new policy."""
        return AdaptiveRoleExecutor(
            role=role,
            prompt_version=prompt_version,
            budget=self._budget,
            delegate_factory=delegate_factory,
            envelope=envelope,
        )
