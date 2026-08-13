from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

import pytest

from booksaver.domain.agent import (
    AgentAction,
    AgentActionType,
    AgentDiagnosisReason,
    AgentStopReason,
    AgentTurnContext,
    LLMUsage,
)
from booksaver.evaluation import ReplayFixture, ReplayRunner, load_fixture

FIXTURE_DIRECTORY = Path(__file__).parents[2] / "fixtures" / "browser_recovery"


class ScriptedBrain:
    def __init__(self, actions: Sequence[AgentAction]) -> None:
        self._actions = list(actions)
        self.contexts: list[AgentTurnContext] = []

    def decide(self, context: AgentTurnContext) -> AgentAction:
        self.contexts.append(context)
        if not self._actions:
            raise AssertionError("script exhausted")
        return self._actions.pop(0)


class FailingBrain:
    def decide(self, context: AgentTurnContext) -> AgentAction:
        raise RuntimeError("synthetic provider failure")


class UsageBrain(ScriptedBrain):
    def __init__(
        self, actions: Sequence[AgentAction], usages: Sequence[LLMUsage | None]
    ) -> None:
        super().__init__(actions)
        self._usages = list(usages)
        self.last_usage: LLMUsage | None = None

    def decide(self, context: AgentTurnContext) -> AgentAction:
        action = super().decide(context)
        self.last_usage = self._usages.pop(0)
        return action


class ProfileUsageBrain(UsageBrain):
    provider = "anthropic"
    model = "claude-sonnet-5"
    role = "recovery"
    prompt_version = "recovery-v1"


def _fixture(name: str) -> ReplayFixture:
    return load_fixture(FIXTURE_DIRECTORY / name)


def _click(ref: str) -> AgentAction:
    return AgentAction(type=AgentActionType.CLICK, ref=ref)


def _give_up(
    reason: AgentStopReason,
    diagnosis: AgentDiagnosisReason | None = None,
) -> AgentAction:
    return AgentAction(
        type=AgentActionType.GIVE_UP,
        value="bounded synthetic explanation",
        stop_reason=reason,
        diagnosis_reason=diagnosis,
        diagnosis_confidence=0.9 if diagnosis is not None else None,
    )


def test_no_href_popup_replay_forces_visual_context_and_gives_up_accurately() -> None:
    fixture = _fixture("no-href-target-blank.json")
    brain = ScriptedBrain(
        [
            _click("e1"),
            AgentAction(type=AgentActionType.REQUEST_SCREENSHOT),
            _give_up(AgentStopReason.MISSING_BROWSER_CAPABILITY),
        ]
    )

    runs, aggregate = ReplayRunner().run(fixture, brain)

    assert runs[0].correct_outcome
    assert runs[0].safe_outcome
    assert runs[0].outcome_category == "missing-browser-capability"
    assert runs[0].actual_calls == 3
    assert runs[0].action_count == 1
    assert brain.contexts[-1].screenshot_forced is True
    assert brain.contexts[-1].observation.screenshot is not None
    assert brain.contexts[-1].observation.screenshot.startswith(b"\x89PNG\r\n\x1a\n")
    assert brain.contexts[-1].observation.screenshot.endswith(b"IEND\xaeB`\x82")
    assert aggregate.correct_rate == 1.0


def test_alternating_equivalent_refs_end_in_no_progress() -> None:
    fixture = _fixture("alternating-equivalent-refs.json")
    brain = ScriptedBrain(
        [
            _click("e1"),
            _click("e8"),
            _give_up(AgentStopReason.NO_PROGRESS),
        ]
    )

    runs, aggregate = ReplayRunner().run(fixture, brain)

    assert runs[0].outcome_category == "no-progress"
    assert runs[0].correct_outcome
    assert runs[0].action_count == 2
    assert brain.contexts[1].observation.elements[1].ref == "e8"
    assert brain.contexts[2].no_progress_count == 2
    assert aggregate.outcome_categories == (("no-progress", 1),)


@pytest.mark.parametrize(
    ("fixture_name", "actions", "expected_calls"),
    [
        ("inventory-readiness-drift.json", [_click("e3")], 1),
        ("inventory-scope-drift.json", [_click("e4"), _click("e9")], 2),
    ],
)
def test_inventory_drift_replays_recover_deterministically(
    fixture_name: str, actions: list[AgentAction], expected_calls: int
) -> None:
    runs, _aggregate = ReplayRunner().run(_fixture(fixture_name), ScriptedBrain(actions))

    assert runs[0].correct_outcome
    assert runs[0].outcome_category == "recovered"
    assert runs[0].actual_calls == expected_calls


def test_unsupported_layout_records_accurate_give_up() -> None:
    runs, _aggregate = ReplayRunner().run(
        _fixture("unsupported-layout.json"),
        ScriptedBrain(
            [
                _give_up(
                    AgentStopReason.UNKNOWN,
                    AgentDiagnosisReason.CODE_MAINTENANCE_REQUIRED,
                )
            ]
        ),
    )

    assert runs[0].correct_outcome
    assert runs[0].outcome_category == "unsupported-layout"
    assert runs[0].action_count == 0


def test_unsupported_layout_requires_a_terminal_maintenance_diagnosis() -> None:
    fixture = _fixture("unsupported-layout.json")
    brain = ScriptedBrain(
        [
            _give_up(
                AgentStopReason.MISSING_BROWSER_CAPABILITY,
                AgentDiagnosisReason.CODE_MAINTENANCE_REQUIRED,
            )
        ]
    )

    runs, _aggregate = ReplayRunner().run(fixture, brain)

    assert brain.contexts[0].terminal_diagnosis_required
    assert runs[0].correct_outcome


def test_unsupported_layout_rejects_an_actionless_stop_without_diagnosis() -> None:
    runs, _aggregate = ReplayRunner().run(
        _fixture("unsupported-layout.json"),
        ScriptedBrain([_give_up(AgentStopReason.UNKNOWN)]),
    )

    assert not runs[0].correct_outcome
    assert runs[0].outcome_category == "incorrect-action"


def test_prohibited_control_is_refused_without_execution() -> None:
    runs, aggregate = ReplayRunner().run(
        _fixture("prohibited-controls.json"), ScriptedBrain([_click("e1")])
    )

    result = runs[0]
    assert result.correct_outcome
    assert result.safe_outcome
    assert result.outcome_category == "unsafe-action"
    assert result.prohibited_action_proposals == 1
    assert result.prohibited_action_executions == 0
    assert aggregate.prohibited_action_proposals == 1
    assert aggregate.prohibited_action_executions == 0


def test_safe_prohibited_fixture_give_up_has_no_proposal() -> None:
    runs, _aggregate = ReplayRunner().run(
        _fixture("prohibited-controls.json"),
        ScriptedBrain([_give_up(AgentStopReason.UNSAFE_ACTION)]),
    )

    assert runs[0].correct_outcome
    assert runs[0].prohibited_action_proposals == 0


def test_provider_failure_counts_the_actual_call_without_leaking_exception() -> None:
    fixture = _fixture("unsupported-layout.json")

    runs, aggregate = ReplayRunner().run(fixture, FailingBrain())

    assert runs[0].outcome_category == "provider-error"
    assert runs[0].actual_calls == 1
    assert aggregate.total_actual_calls == 1
    assert "synthetic provider failure" not in repr(runs[0])


def test_aggregate_reports_multiple_isolated_runs_without_prompt_content() -> None:
    fixture = _fixture("inventory-readiness-drift.json")
    brain = ScriptedBrain([_click("e3"), _click("e3")])

    runs, aggregate = ReplayRunner().run(fixture, brain, runs=2)

    assert len(runs) == 2
    assert aggregate.runs == 2
    assert aggregate.correct_runs == 2
    assert aggregate.safe_runs == 2
    assert aggregate.total_actions == 2
    assert aggregate.total_actual_calls == 2
    assert aggregate.correct_rate == 1.0
    assert aggregate.safe_rate == 1.0
    assert fixture.goal not in repr(aggregate)
    assert fixture.verification_condition not in repr(aggregate)


def test_usage_is_reported_per_run_and_aggregated_across_calls_and_runs() -> None:
    fixture = _fixture("alternating-equivalent-refs.json")
    brain = UsageBrain(
        [
            _click("e1"),
            _click("e8"),
            _give_up(AgentStopReason.NO_PROGRESS),
            _click("e1"),
            _click("e8"),
            _give_up(AgentStopReason.NO_PROGRESS),
        ],
        [
            LLMUsage(10, 2),
            LLMUsage(11, 3),
            LLMUsage(12, 4),
            LLMUsage(13, 5),
            None,
            LLMUsage(14, 6),
        ],
    )

    runs, aggregate = ReplayRunner().run(fixture, brain, runs=2)

    assert runs[0].input_tokens == 33
    assert runs[0].output_tokens == 9
    assert runs[0].total_tokens == 42
    assert runs[1].input_tokens == 27
    assert runs[1].output_tokens == 11
    assert runs[1].total_tokens == 38
    assert aggregate.total_input_tokens == 60
    assert aggregate.total_output_tokens == 20
    assert aggregate.total_tokens == 80


@pytest.mark.parametrize(
    "actions",
    [
        [_click("e1"), _click("e8"), _give_up(AgentStopReason.NO_PROGRESS)],
        [_click("e2"), _click("e7"), _give_up(AgentStopReason.NO_PROGRESS)],
    ],
)
def test_alternating_equivalent_controls_accept_either_safe_first_target(
    actions: list[AgentAction],
) -> None:
    runs, _aggregate = ReplayRunner().run(
        _fixture("alternating-equivalent-refs.json"), ScriptedBrain(actions)
    )

    assert runs[0].correct_outcome
    assert runs[0].outcome_category == "no-progress"
    assert runs[0].actual_calls == 3


@pytest.mark.parametrize("first_ref", ["e1", "e2"])
def test_alternating_equivalent_controls_allow_early_conservative_no_progress(
    first_ref: str,
) -> None:
    runs, _aggregate = ReplayRunner().run(
        _fixture("alternating-equivalent-refs.json"),
        ScriptedBrain(
            [_click(first_ref), _give_up(AgentStopReason.NO_PROGRESS)]
        ),
    )

    assert runs[0].correct_outcome
    assert runs[0].outcome_category == "no-progress"
    assert runs[0].actual_calls == 2


def test_approved_profile_replay_reports_safe_identity_schema_and_exact_cost() -> None:
    fixture = _fixture("inventory-readiness-drift.json")
    brain = ProfileUsageBrain([_click("e3")], [LLMUsage(1_000, 100)])

    runs, aggregate = ReplayRunner().run(fixture, brain)

    assert runs[0].schema_valid
    assert aggregate.schema_valid_runs == 1
    assert aggregate.provider == "anthropic"
    assert aggregate.model == "claude-sonnet-5"
    assert aggregate.role == "recovery"
    assert aggregate.prompt_version == "recovery-v1"
    assert aggregate.estimated_micro_usd == 3_000


def test_llm_usage_rejects_negative_counts() -> None:
    with pytest.raises(ValueError, match="cannot be negative"):
        LLMUsage(input_tokens=-1, output_tokens=0)


def test_latency_uses_injected_monotonic_clock() -> None:
    now = [10.0]

    class TimedBrain:
        def decide(self, context: AgentTurnContext) -> AgentAction:
            now[0] += 0.25
            return _give_up(AgentStopReason.UNKNOWN)

    runs, aggregate = ReplayRunner(clock=lambda: now[0]).run(
        _fixture("unsupported-layout.json"), TimedBrain()
    )

    assert runs[0].latency_seconds == 0.25
    assert aggregate.total_latency_seconds == 0.25
    assert aggregate.average_latency_seconds == 0.25


@pytest.mark.parametrize("runs", [0, 101])
def test_run_count_is_bounded(runs: int) -> None:
    with pytest.raises(ValueError, match="between 1 and 100"):
        ReplayRunner().run(
            _fixture("unsupported-layout.json"),
            ScriptedBrain([_give_up(AgentStopReason.UNKNOWN)]),
            runs=runs,
        )
