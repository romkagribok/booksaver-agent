"""Deterministic replay of sanitized observations against an ``AgentBrain``."""

from __future__ import annotations

import base64
import time
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass, replace

from booksaver.application.ports import AgentBrain
from booksaver.domain.agent import (
    AgentActionType,
    AgentTurnContext,
    LLMUsage,
    blocked_action_reason,
)
from booksaver.domain.model_policy import (
    AdaptiveModelPortfolio,
    ModelCostEstimator,
    ModelRole,
    TokenEnvelope,
)

from .fixtures import ReplayFixture

_EXECUTABLE_ACTIONS = frozenset(
    {
        AgentActionType.CLICK,
        AgentActionType.FILL,
        AgentActionType.SELECT,
        AgentActionType.SCROLL,
        AgentActionType.EXTRACT,
    }
)
_SANITIZED_SCREENSHOT = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42Y"
    "AAAAASUVORK5CYII="
)


class ReplayExecutionStopped(RuntimeError):
    """Typed controller stop that occurs before a provider call starts."""

    def __init__(self, outcome_category: str) -> None:
        super().__init__(outcome_category)
        self.outcome_category = outcome_category


@dataclass(frozen=True)
class ReplayRunMetrics:
    correct_outcome: bool
    safe_outcome: bool
    action_count: int
    actual_calls: int
    input_tokens: int
    output_tokens: int
    latency_seconds: float
    outcome_category: str
    prohibited_action_proposals: int
    prohibited_action_executions: int = 0
    schema_valid: bool = True
    provider: str | None = None
    model: str | None = None
    role: str | None = None
    prompt_version: str | None = None
    estimated_micro_usd: int = 0

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


@dataclass(frozen=True)
class ReplayAggregateMetrics:
    fixture_id: str
    runs: int
    correct_runs: int
    safe_runs: int
    total_actions: int
    total_actual_calls: int
    total_input_tokens: int
    total_output_tokens: int
    total_latency_seconds: float
    average_latency_seconds: float
    outcome_categories: tuple[tuple[str, int], ...]
    prohibited_action_proposals: int
    prohibited_action_executions: int
    schema_valid_runs: int = 0
    provider: str | None = None
    model: str | None = None
    role: str | None = None
    prompt_version: str | None = None
    estimated_micro_usd: int = 0

    @property
    def correct_rate(self) -> float:
        return self.correct_runs / self.runs

    @property
    def safe_rate(self) -> float:
        return self.safe_runs / self.runs

    @property
    def total_tokens(self) -> int:
        return self.total_input_tokens + self.total_output_tokens


class ReplayRunner:
    """Run a fixture without browser, network, database, or prompt rendering.

    Each ``AgentBrain.decide`` invocation is one actual LLM call. Fixture transitions
    simulate only sanitized visible outcomes. Guarded actions are classified and stopped
    before a transition, so this evaluator cannot execute a prohibited browser action.
    """

    def __init__(self, clock: Callable[[], float] = time.perf_counter) -> None:
        self._clock = clock

    def run(
        self,
        fixture: ReplayFixture,
        brain: AgentBrain,
        *,
        runs: int = 1,
    ) -> tuple[tuple[ReplayRunMetrics, ...], ReplayAggregateMetrics]:
        if not 1 <= runs <= 100:
            raise ValueError("runs must be between 1 and 100")
        collected: list[ReplayRunMetrics] = []
        for _ in range(runs):
            collected.append(self._run_once(fixture, brain))
            if bool(getattr(brain, "terminal_replay_stop", False)):
                break
        results = tuple(collected)
        categories = Counter(result.outcome_category for result in results)
        total_latency = sum(result.latency_seconds for result in results)
        aggregate = ReplayAggregateMetrics(
            fixture_id=fixture.fixture_id,
            runs=len(results),
            correct_runs=sum(result.correct_outcome for result in results),
            safe_runs=sum(result.safe_outcome for result in results),
            total_actions=sum(result.action_count for result in results),
            total_actual_calls=sum(result.actual_calls for result in results),
            total_input_tokens=sum(result.input_tokens for result in results),
            total_output_tokens=sum(result.output_tokens for result in results),
            total_latency_seconds=total_latency,
            average_latency_seconds=total_latency / len(results),
            outcome_categories=tuple(sorted(categories.items())),
            prohibited_action_proposals=sum(
                result.prohibited_action_proposals for result in results
            ),
            prohibited_action_executions=sum(
                result.prohibited_action_executions for result in results
            ),
            schema_valid_runs=sum(result.schema_valid for result in results),
            provider=_safe_adapter_code(brain, "provider"),
            model=_safe_adapter_code(brain, "model"),
            role=_safe_adapter_code(brain, "role"),
            prompt_version=_safe_adapter_code(brain, "prompt_version"),
            estimated_micro_usd=sum(result.estimated_micro_usd for result in results),
        )
        return results, aggregate

    def _run_once(self, fixture: ReplayFixture, brain: AgentBrain) -> ReplayRunMetrics:
        started = self._clock()
        state_id = fixture.start_state
        actual_calls = 0
        input_tokens = 0
        output_tokens = 0
        action_count = 0
        prohibited_proposals = 0
        outcome_category = "budget-exhausted"
        schema_valid = True

        while actual_calls < fixture.max_calls:
            elapsed = self._clock() - started
            if elapsed > fixture.timeout_seconds:
                outcome_category = "timeout"
                break
            state = fixture.state(state_id)
            observation = state.observation
            if state.screenshot_forced:
                observation = replace(observation, screenshot=_SANITIZED_SCREENSHOT)
            context = AgentTurnContext(
                goal=fixture.goal,
                observation=observation,
                history=state.history,
                llm_calls_used=actual_calls,
                max_llm_calls=fixture.max_calls,
                no_progress_count=state.no_progress_count,
                screenshot_forced=state.screenshot_forced,
                seconds_remaining=max(0.0, fixture.timeout_seconds - elapsed),
                verification_condition=fixture.verification_condition,
            )
            try:
                action = brain.decide(context)
            except ReplayExecutionStopped as exc:
                outcome_category = exc.outcome_category
                break
            except Exception:
                actual_calls += 1
                usage = getattr(brain, "last_usage", None)
                if isinstance(usage, LLMUsage):
                    input_tokens += usage.input_tokens
                    output_tokens += usage.output_tokens
                outcome_category = "provider-error"
                schema_valid = False
                break
            actual_calls += 1
            usage = getattr(brain, "last_usage", None)
            if isinstance(usage, LLMUsage):
                input_tokens += usage.input_tokens
                output_tokens += usage.output_tokens
            if action.type in _EXECUTABLE_ACTIONS:
                action_count += 1

            blocked = blocked_action_reason(action, observation)
            if blocked is not None:
                prohibited_proposals += 1
                outcome_category = "unsafe-action"
                break

            transition = next(
                (
                    item
                    for item in state.transitions
                    if item.expectation.matches(action, observation)
                ),
                None,
            )
            if transition is None:
                outcome_category = "incorrect-action"
                break
            if transition.terminal_category is not None:
                outcome_category = transition.terminal_category
                break
            assert transition.next_state is not None
            state_id = transition.next_state

        latency = max(0.0, self._clock() - started)
        prohibited_executions = 0
        provider = _safe_adapter_code(brain, "provider")
        model = _safe_adapter_code(brain, "model")
        role = _safe_adapter_code(brain, "role")
        prompt_version = _safe_adapter_code(brain, "prompt_version")
        estimated_micro_usd = _estimate_approved_cost(
            model=model,
            role=role,
            prompt_version=prompt_version,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )
        return ReplayRunMetrics(
            correct_outcome=outcome_category in fixture.expected_outcome_categories,
            safe_outcome=prohibited_executions == 0,
            action_count=action_count,
            actual_calls=actual_calls,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            latency_seconds=latency,
            outcome_category=outcome_category,
            prohibited_action_proposals=prohibited_proposals,
            prohibited_action_executions=prohibited_executions,
            schema_valid=schema_valid,
            provider=provider,
            model=model,
            role=role,
            prompt_version=prompt_version,
            estimated_micro_usd=estimated_micro_usd,
        )


def _safe_adapter_code(adapter: object, attribute: str) -> str | None:
    value = getattr(adapter, attribute, None)
    if not isinstance(value, str) or not value:
        return None
    if len(value) > 128 or any(not (char.isalnum() or char in "._:-") for char in value):
        return None
    return value


def _estimate_approved_cost(
    *,
    model: str | None,
    role: str | None,
    prompt_version: str | None,
    input_tokens: int,
    output_tokens: int,
) -> int:
    if model not in {"claude-sonnet-5", "claude-opus-5"}:
        return 0
    try:
        model_role = ModelRole(role or ModelRole.RECOVERY.value)
    except ValueError:
        model_role = ModelRole.RECOVERY
    portfolio = AdaptiveModelPortfolio()
    profile = (
        portfolio.primary(model_role, prompt_version or "unversioned")
        if model == portfolio.primary_model
        else portfolio.escalation(model_role, prompt_version or "unversioned")
    )
    return ModelCostEstimator().estimate(
        profile, TokenEnvelope(input_tokens, output_tokens)
    ).micro_usd
