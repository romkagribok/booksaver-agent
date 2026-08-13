"""Privacy-safe live qualification for the fixed adaptive model portfolio.

Qualification is deliberately separate from ordinary replay.  It only accepts the
packaged, reviewed fixture corpus, runs every fixture exactly ten times for both
approved profiles, and admits each physical call against operator-supplied and
deployment-day cost caps before contacting the provider.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime

from booksaver.application.model_policy import BrowserJobCostBudget
from booksaver.application.ports import AgentBrain
from booksaver.domain.agent import AgentAction, AgentTurnContext, LLMUsage
from booksaver.domain.model_policy import (
    AdaptiveModelPortfolio,
    EscalationTrigger,
    ModelAttemptOutcome,
    ModelAttemptPlan,
    ModelCostEstimator,
    ModelProfile,
    ModelRole,
    ModelTier,
    QualificationDuty,
    QualificationEvaluator,
    QualificationMetrics,
    QualificationResult,
    TokenEnvelope,
    UsdAmount,
)
from booksaver.infrastructure.llm.anthropic_adapter import (
    AGENT_PROMPT_VERSION,
    render_agent_turn_context,
)

from .fixtures import ReplayFixture
from .replay import ReplayAggregateMetrics, ReplayExecutionStopped, ReplayRunner

PACKAGED_QUALIFICATION_VERSION = "browser-recovery-v4"
QUALIFICATION_RUNS_PER_FIXTURE = 10

# Covers the current system message, tool schemas, API framing, and the fixture's
# one-pixel sanitized image.  The rendered user context is added byte-for-token,
# which is intentionally conservative for the packaged UTF-8 fixtures.
_PROVIDER_PROTOCOL_OVERHEAD_TOKENS = 8_192
_MAX_OUTPUT_TOKENS_PER_CALL = 1_024


@dataclass(frozen=True, slots=True)
class QualificationPlan:
    fixture_count: int
    runs_per_fixture: int
    maximum_provider_calls: int
    maximum_cost: UsdAmount


@dataclass(frozen=True, slots=True)
class ProfileQualificationReport:
    profile_identity: str
    model: str
    duty: QualificationDuty
    fixture_version: str
    fixtures: tuple[ReplayAggregateMetrics, ...]
    total_actions: int
    result: QualificationResult


@dataclass(frozen=True, slots=True)
class PortfolioQualificationReport:
    plan: QualificationPlan
    profiles: tuple[ProfileQualificationReport, ...]
    stopped_reason: str | None = None

    @property
    def passed(self) -> bool:
        return self.stopped_reason is None and len(self.profiles) == 2 and all(
            profile.result.is_approved for profile in self.profiles
        )

    @property
    def estimated_cost(self) -> UsdAmount:
        return UsdAmount(
            sum(
                profile.result.metrics.estimated_cost.micro_usd
                for profile in self.profiles
            )
        )


@dataclass(frozen=True, slots=True)
class _QualificationLane:
    profile: ModelProfile
    duty: QualificationDuty
    fixtures: tuple[ReplayFixture, ...]


def approved_recovery_profiles() -> tuple[ModelProfile, ModelProfile]:
    """Return the only two profiles eligible for production qualification."""
    portfolio = AdaptiveModelPortfolio()
    return (
        portfolio.primary(ModelRole.RECOVERY, AGENT_PROMPT_VERSION),
        portfolio.escalation(ModelRole.RECOVERY, AGENT_PROMPT_VERSION),
    )


def plan_packaged_qualification(
    fixtures: Sequence[ReplayFixture],
) -> QualificationPlan:
    """Price the production-duty matrix rather than a cross-profile Cartesian run."""
    lanes = _packaged_qualification_lanes(fixtures)
    estimator = ModelCostEstimator()
    maximum_cost = UsdAmount()
    maximum_calls = 0
    for lane in lanes:
        for fixture in lane.fixtures:
            call_count = fixture.max_calls * QUALIFICATION_RUNS_PER_FIXTURE
            maximum_calls += call_count
            maximum_cost += UsdAmount(
                estimator.estimate(
                    lane.profile, _fixture_call_envelope(fixture)
                ).micro_usd
                * call_count
            )
    return QualificationPlan(
        fixture_count=sum(len(lane.fixtures) for lane in lanes),
        runs_per_fixture=QUALIFICATION_RUNS_PER_FIXTURE,
        maximum_provider_calls=maximum_calls,
        maximum_cost=maximum_cost,
    )


def _packaged_qualification_lanes(
    fixtures: Sequence[ReplayFixture],
) -> tuple[_QualificationLane, _QualificationLane]:
    if not fixtures:
        raise ValueError("packaged qualification requires fixtures")
    fixture_ids = tuple(fixture.fixture_id for fixture in fixtures)
    if len(fixture_ids) != len(set(fixture_ids)):
        raise ValueError("packaged qualification fixture ids must be unique")
    sonnet, opus = approved_recovery_profiles()
    if sonnet.tier is not ModelTier.SONNET or opus.tier is not ModelTier.OPUS:
        raise ValueError("packaged qualification portfolio duties are invalid")
    recovery = tuple(
        fixture for fixture in fixtures if not fixture.terminal_diagnosis_required
    )
    diagnosis = tuple(
        fixture for fixture in fixtures if fixture.terminal_diagnosis_required
    )
    if not recovery:
        raise ValueError(
            "packaged qualification requires a primary-recovery fixture"
        )
    if not diagnosis:
        raise ValueError(
            "packaged qualification requires a terminal-diagnosis fixture"
        )
    return (
        _QualificationLane(
            profile=sonnet,
            duty=QualificationDuty.PRIMARY_RECOVERY,
            fixtures=recovery,
        ),
        _QualificationLane(
            profile=opus,
            duty=QualificationDuty.TERMINAL_DIAGNOSIS,
            fixtures=diagnosis,
        ),
    )


def plan_profile_replay(
    fixtures: Sequence[ReplayFixture],
    profiles: Sequence[ModelProfile],
    *,
    runs_per_fixture: int,
) -> QualificationPlan:
    """Price a bounded replay plan before any model adapter is constructed."""
    if not fixtures:
        raise ValueError("evaluation requires at least one fixture")
    if not profiles:
        raise ValueError("evaluation requires at least one approved profile")
    if not 1 <= runs_per_fixture <= QUALIFICATION_RUNS_PER_FIXTURE:
        raise ValueError("evaluation runs per fixture must be between 1 and 10")
    estimator = ModelCostEstimator()
    maximum_cost = UsdAmount()
    maximum_calls = 0
    for fixture in fixtures:
        call_count = fixture.max_calls * runs_per_fixture
        maximum_calls += call_count * len(profiles)
        envelope = _fixture_call_envelope(fixture)
        for profile in profiles:
            maximum_cost += UsdAmount(
                estimator.estimate(profile, envelope).micro_usd * call_count
            )
    return QualificationPlan(
        fixture_count=len(fixtures),
        runs_per_fixture=runs_per_fixture,
        maximum_provider_calls=maximum_calls,
        maximum_cost=maximum_cost,
    )


def run_packaged_qualification(
    fixtures: Sequence[ReplayFixture],
    brain_factory: Callable[[ModelProfile], AgentBrain],
    *,
    evaluation_cost_limit: UsdAmount,
    budget: BrowserJobCostBudget | None = None,
    runner: ReplayRunner | None = None,
    now: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> PortfolioQualificationReport:
    """Run the fixed corpus under per-call persistent cost admission.

    No fixture content or model response is returned by this coordinator.  Reports
    contain bounded identifiers and aggregate numbers only.
    """
    if evaluation_cost_limit.micro_usd < 1:
        raise ValueError("evaluation_cost_limit must be greater than zero")
    plan = plan_packaged_qualification(fixtures)

    replay_runner = runner or ReplayRunner()
    evaluator = QualificationEvaluator()
    reports: list[ProfileQualificationReport] = []
    stopped_reason: str | None = None
    for lane in _packaged_qualification_lanes(fixtures):
        profile = lane.profile
        delegate = brain_factory(profile)
        brain: AgentBrain = (
            BudgetedQualificationBrain(delegate, profile, lane.duty, budget)
            if budget is not None
            else delegate
        )
        aggregates_list: list[ReplayAggregateMetrics] = []
        for fixture in lane.fixtures:
            aggregate = replay_runner.run(
                fixture,
                brain,
                runs=QUALIFICATION_RUNS_PER_FIXTURE,
            )[1]
            aggregates_list.append(aggregate)
            stop = getattr(brain, "terminal_stop_reason", None)
            if isinstance(stop, str):
                stopped_reason = stop
                break
        aggregates = tuple(aggregates_list)
        total_runs = sum(item.runs for item in aggregates)
        diagnosis_runs = (
            total_runs
            if lane.duty is QualificationDuty.TERMINAL_DIAGNOSIS
            else 0
        )
        diagnosis_correct = (
            sum(item.correct_runs for item in aggregates)
            if lane.duty is QualificationDuty.TERMINAL_DIAGNOSIS
            else 0
        )
        metrics = QualificationMetrics(
            runs=total_runs,
            correct_runs=sum(item.correct_runs for item in aggregates),
            diagnosis_runs=diagnosis_runs,
            diagnosis_correct_runs=diagnosis_correct,
            schema_valid_runs=sum(item.schema_valid_runs for item in aggregates),
            prohibited_action_proposals=sum(
                item.prohibited_action_proposals for item in aggregates
            ),
            prohibited_action_executions=sum(
                item.prohibited_action_executions for item in aggregates
            ),
            escalation_count=(
                total_runs
                if lane.duty is QualificationDuty.TERMINAL_DIAGNOSIS
                else 0
            ),
            total_calls=sum(item.total_actual_calls for item in aggregates),
            total_actions=sum(item.total_actions for item in aggregates),
            input_tokens=sum(item.total_input_tokens for item in aggregates),
            output_tokens=sum(item.total_output_tokens for item in aggregates),
            latency_ms=round(
                sum(item.total_latency_seconds for item in aggregates) * 1_000
            ),
            estimated_cost=UsdAmount(
                sum(item.estimated_micro_usd for item in aggregates)
            ),
        )
        result = evaluator.evaluate(
            profile_identity=profile.identity,
            fixture_version=PACKAGED_QUALIFICATION_VERSION,
            metrics=metrics,
            created_at=now(),
            required_fixture_results=tuple(
                next(
                    (
                        (item.runs, item.correct_runs)
                        for item in aggregates
                        if item.fixture_id == fixture.fixture_id
                    ),
                    (0, 0),
                )
                for fixture in lane.fixtures
            ),
        )
        reports.append(
            ProfileQualificationReport(
                profile_identity=profile.identity,
                model=profile.model_id,
                duty=lane.duty,
                fixture_version=PACKAGED_QUALIFICATION_VERSION,
                fixtures=aggregates,
                total_actions=metrics.total_actions,
                result=result,
            )
        )
        if stopped_reason is not None:
            break

    report = PortfolioQualificationReport(
        plan=plan,
        profiles=tuple(reports),
        stopped_reason=stopped_reason,
    )
    if report.estimated_cost > evaluation_cost_limit:
        return PortfolioQualificationReport(
            plan=report.plan,
            profiles=report.profiles,
            stopped_reason="evaluation_cost_limit_overrun",
        )
    return report


class BudgetedQualificationBrain:
    """Charge every physical replay call to the shared deployment spend ledger."""

    def __init__(
        self,
        delegate: AgentBrain,
        profile: ModelProfile,
        duty: QualificationDuty,
        budget: BrowserJobCostBudget,
    ) -> None:
        self._delegate = delegate
        self._profile = profile
        self._duty = duty
        self._budget = budget
        self.last_usage: LLMUsage | None = None
        self.terminal_replay_stop = False
        self.terminal_stop_reason: str | None = None
        self.provider = getattr(delegate, "provider", profile.provider.value)
        self.model = profile.model_id
        self.role = getattr(delegate, "role", profile.role.value)
        self.prompt_version = getattr(delegate, "prompt_version", profile.prompt_version)

    def decide(self, context: AgentTurnContext) -> AgentAction:
        envelope = _context_call_envelope(context)
        admission = self._budget.admit(
            ModelAttemptPlan(
                ordinal=1,
                profile=self._profile,
                trigger=(
                    EscalationTrigger.INITIAL_AMBIGUOUS
                    if self._duty is QualificationDuty.PRIMARY_RECOVERY
                    else EscalationTrigger.UNVERIFIED_SONNET_EXHAUSTION
                ),
            ),
            envelope,
        )
        if admission.attempt is None:
            assert admission.stop_reason is not None
            self.terminal_replay_stop = True
            self.terminal_stop_reason = (
                "evaluation_cost_limit"
                if admission.stop_reason.value == "job_cost_limit"
                else admission.stop_reason.value
            )
            raise ReplayExecutionStopped(self.terminal_stop_reason)

        started = time.perf_counter()
        self.last_usage = None
        try:
            action = self._delegate.decide(context)
            usage = getattr(self._delegate, "last_usage", None)
            self.last_usage = usage if isinstance(usage, LLMUsage) else None
        except Exception:
            usage = getattr(self._delegate, "last_usage", None)
            self.last_usage = usage if isinstance(usage, LLMUsage) else None
            self._budget.reconcile(
                admission.attempt,
                usage=self.last_usage,
                latency_ms=round((time.perf_counter() - started) * 1_000),
                outcome=ModelAttemptOutcome.PROVIDER_FAILED,
            )
            raise
        self._budget.reconcile(
            admission.attempt,
            usage=self.last_usage,
            latency_ms=round((time.perf_counter() - started) * 1_000),
            outcome=(
                ModelAttemptOutcome.COMPLETED
                if self._duty is QualificationDuty.PRIMARY_RECOVERY
                else ModelAttemptOutcome.DIAGNOSED
            ),
        )
        return action


def _fixture_call_envelope(fixture: ReplayFixture) -> TokenEnvelope:
    rendered_bytes = max(
        len(
            render_agent_turn_context(
                AgentTurnContext(
                    goal=fixture.goal,
                    observation=state.observation,
                    history=state.history,
                    llm_calls_used=fixture.max_calls - 1,
                    max_llm_calls=fixture.max_calls,
                    no_progress_count=state.no_progress_count,
                    screenshot_forced=state.screenshot_forced,
                    seconds_remaining=fixture.timeout_seconds,
                    verification_condition=fixture.verification_condition,
                    terminal_diagnosis_required=fixture.terminal_diagnosis_required,
                )
            ).encode("utf-8")
        )
        for state in fixture.states
    )
    return TokenEnvelope(
        maximum_input_tokens=rendered_bytes + _PROVIDER_PROTOCOL_OVERHEAD_TOKENS,
        maximum_output_tokens=_MAX_OUTPUT_TOKENS_PER_CALL,
    )


def _context_call_envelope(context: AgentTurnContext) -> TokenEnvelope:
    return TokenEnvelope(
        maximum_input_tokens=(
            len(render_agent_turn_context(context).encode("utf-8"))
            + _PROVIDER_PROTOCOL_OVERHEAD_TOKENS
        ),
        maximum_output_tokens=_MAX_OUTPUT_TOKENS_PER_CALL,
    )
