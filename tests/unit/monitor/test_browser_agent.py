from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest

from booksaver.domain.agent import (
    AgentAction,
    AgentActionType,
    AgentBudget,
    AgentHistoryOutcome,
    AgentSettings,
    AgentStopReason,
    ElementInfo,
    RecoveryPolicy,
    TraceKind,
)
from booksaver.domain.check_result import CheckResult, FailureCode, FailureReason
from booksaver.domain.errors import UserKeyInvalidError
from booksaver.domain.journey import JourneyStep
from booksaver.monitor.browser_agent import BrowserAgent
from booksaver.monitor.trace import TraceRecorder

from .fakes import FakeAgentBrain, FakeInteractiveBrowser


def _click(ref: str = "e0") -> AgentAction:
    return AgentAction(type=AgentActionType.CLICK, ref=ref)


def _agent(
    browser: FakeInteractiveBrowser,
    script: list[AgentAction],
    settings: AgentSettings | None = None,
) -> tuple[BrowserAgent, FakeAgentBrain, TraceRecorder]:
    brain = FakeAgentBrain(script)
    recorder = TraceRecorder("b-1")
    agent = BrowserAgent(
        browser, brain, AgentBudget(settings or AgentSettings()), recorder
    )
    return agent, brain, recorder


def _browser() -> FakeInteractiveBrowser:
    browser = FakeInteractiveBrowser()
    browser.elements = (
        ElementInfo(ref="e0", role="button", label="Search"),
        ElementInfo(ref="e1", role="button", label="Book now"),
    )
    return browser


class TestScreenshotRequestCap:
    def test_repeated_screenshot_requests_are_denied_then_give_up(self):
        req = AgentAction(type=AgentActionType.REQUEST_SCREENSHOT)
        agent, brain, _ = _agent(_browser(), [req] * 8)
        result = agent.complete_step(
            JourneyStep.FILL_SEARCH, "goal", verify=lambda: False, trigger="boom"
        )
        assert result.failure_code is FailureCode.AGENT_NO_PROGRESS
        assert result.stop_reason is AgentStopReason.NO_PROGRESS
        assert result.used_screenshot
        assert len(brain.decisions) == 4


class TestLoopDetection:
    def test_repeated_identical_action_gives_up_before_budget(self):
        browser = _browser()
        agent, brain, _ = _agent(browser, [_click()] * 10)
        result = agent.complete_step(
            JourneyStep.FILL_SEARCH, "goal", verify=lambda: False, trigger="boom"
        )
        assert result.failure_code is FailureCode.AGENT_NO_PROGRESS
        assert "screenshot" in result.detail.lower()
        assert len(brain.decisions) == 3
        # Two unchanged executions force a screenshot; the third semantic
        # duplicate is refused without another browser action.
        executed = [detail for kind, detail in browser.actions if kind == "act"]
        assert len(executed) == 2

    def test_refused_duplicate_is_traced_and_refreshes_screenshot(self):
        browser = _browser()
        agent, brain, recorder = _agent(browser, [_click()] * 5)
        result = agent.complete_step(
            JourneyStep.FILL_SEARCH, "goal", verify=lambda: False, trigger="boom"
        )
        assert result.failure_code is FailureCode.AGENT_NO_PROGRESS
        # Third proposal sees the forced screenshot and is refused after the
        # first two unchanged semantic executions.
        assert brain.decisions[2].screenshot is not None
        trace = recorder.finish(
            CheckResult.failure(
                "b-1",
                datetime.now(UTC),
                FailureReason(code=result.failure_code, detail=result.detail),
            )
        )
        blocked = next(
            event for event in trace.events if event.kind is TraceKind.AGENT_BLOCKED
        )
        assert set(json.loads(blocked.detail)) == {
            "reason_digest",
            "step",
        }
        assert "repeated semantic action refused" not in blocked.detail
        assert any(event.kind is TraceKind.AGENT_OUTCOME for event in trace.events)

    def test_changed_refs_for_same_semantic_target_share_execution_limit(self):
        browser = _browser()
        browser.elements = (
            ElementInfo(
                ref="e0",
                role="link",
                label="Hotel Test",
                href="https://www.booking.com/hotel/test.html?aid=1",
            ),
        )

        def _renumber(b: FakeInteractiveBrowser, action: AgentAction) -> None:
            next_ref = "e7" if action.ref == "e0" else "e0"
            b.elements = (
                ElementInfo(
                    ref=next_ref,
                    role="link",
                    label="  HOTEL   TEST ",
                    href="https://www.booking.com/hotel/test.html?aid=2",
                ),
            )

        browser.on_act = _renumber
        agent, brain, _ = _agent(
            browser, [_click("e0"), _click("e7"), _click("e0")]
        )

        result = agent.complete_step(
            JourneyStep.OPEN_PROPERTY, "goal", verify=lambda: False, trigger="boom"
        )

        assert result.failure_code is FailureCode.AGENT_NO_PROGRESS
        assert len(brain.decisions) == 3
        assert len([a for a in browser.actions if a[0] == "act"]) == 2

    def test_alternating_actions_cannot_evade_no_progress_screenshot(self):
        browser = _browser()
        browser.elements = (
            ElementInfo(ref="e0", role="button", label="First"),
            ElementInfo(ref="e1", role="button", label="Second"),
        )
        agent, brain, _ = _agent(
            browser, [_click("e0"), _click("e1"), _click("e0")]
        )

        result = agent.complete_step(
            JourneyStep.OPEN_PROPERTY, "goal", verify=lambda: False, trigger="boom"
        )

        assert result.failure_code is FailureCode.AGENT_NO_PROGRESS
        assert brain.decisions[2].screenshot is not None
        assert len([a for a in browser.actions if a[0] == "act"]) == 3

    def test_unrelated_dynamic_page_text_does_not_reset_no_progress_state(self):
        browser = _browser()
        done = {"actions": 0}

        def _advance(b: FakeInteractiveBrowser, action: AgentAction) -> None:
            done["actions"] += 1
            b.page_text = f"state {done['actions']}"

        browser.on_act = _advance
        agent, brain, _ = _agent(browser, [_click()] * 5)

        result = agent.complete_step(
            JourneyStep.FILL_SEARCH,
            "goal",
            verify=lambda: False,
            trigger="boom",
        )

        assert result.failure_code is FailureCode.AGENT_NO_PROGRESS
        assert done["actions"] == 2
        assert len(brain.decisions) == 3
        assert brain.decisions[2].screenshot is not None

    def test_identical_visible_targets_use_stable_occurrence_in_semantic_key(self):
        browser = _browser()
        browser.elements = (
            ElementInfo(ref="e0", role="button", label="See availability"),
            ElementInfo(ref="e1", role="button", label="See availability"),
        )
        agent, _, _ = _agent(
            browser, [_click("e0"), _click("e1"), _click("e0")]
        )

        result = agent.complete_step(
            JourneyStep.OPEN_PROPERTY, "goal", verify=lambda: False, trigger="boom"
        )

        assert result.failure_code is FailureCode.AGENT_NO_PROGRESS
        assert len([action for action in browser.actions if action[0] == "act"]) == 3


class TestLoopOutcomes:
    def test_action_then_verified_success(self):
        browser = _browser()
        done = {"ok": False}
        browser.on_act = lambda b, a: done.update(ok=True)
        agent, _, _ = _agent(browser, [_click()])
        result = agent.complete_step(
            JourneyStep.FILL_SEARCH, "goal", verify=lambda: done["ok"], trigger="boom"
        )
        assert result.ok
        assert not result.used_screenshot

    def test_give_up_maps_to_agent_gave_up(self):
        agent, _, _ = _agent(
            _browser(),
            [AgentAction(type=AgentActionType.GIVE_UP, value="captcha wall")],
        )
        result = agent.complete_step(
            JourneyStep.FILL_SEARCH, "goal", verify=lambda: False, trigger="boom"
        )
        assert not result.ok
        assert result.failure_code is FailureCode.AGENT_GAVE_UP
        assert "captcha wall" in result.detail

    def test_unverified_action_loops_until_script_dry_then_gives_up(self):
        agent, brain, _ = _agent(_browser(), [_click(), _click()])
        result = agent.complete_step(
            JourneyStep.FILL_SEARCH, "goal", verify=lambda: False, trigger="boom"
        )
        assert result.failure_code is FailureCode.AGENT_GAVE_UP
        assert len(brain.decisions) == 3  # 2 clicks + terminal give_up

    def test_script_error_that_already_completed_step_skips_llm(self):
        agent, brain, _ = _agent(_browser(), [_click()])

        result = agent.complete_step(
            "inventory_upcoming", "goal", verify=lambda: True, trigger="late timeout"
        )

        assert result.ok
        assert not brain.decisions

    def test_provider_error_has_distinct_code_and_redacts_message(self):
        browser = _browser()
        brain = FakeAgentBrain(
            [], raise_error=RuntimeError("token=abcdefghijklmnop secret payload")
        )
        recorder = TraceRecorder("b-1")
        agent = BrowserAgent(browser, brain, AgentBudget(AgentSettings()), recorder)

        result = agent.complete_step(
            JourneyStep.FILL_SEARCH, "goal", verify=lambda: False, trigger="boom"
        )

        assert result.failure_code is FailureCode.LLM_ERROR
        assert result.stop_reason is AgentStopReason.PROVIDER_ERROR
        assert "abcdefghijklmnop" not in result.detail
        assert "secret payload" not in result.detail

    def test_personal_key_error_remains_typed_for_caller_guidance(self):
        browser = _browser()
        brain = FakeAgentBrain([], raise_error=UserKeyInvalidError(7, "private"))
        agent = BrowserAgent(
            browser,
            brain,
            AgentBudget(AgentSettings()),
            TraceRecorder("b-1"),
        )

        with pytest.raises(UserKeyInvalidError):
            agent.complete_step(
                JourneyStep.FILL_SEARCH,
                "goal",
                verify=lambda: False,
                trigger="boom",
            )

    def test_provider_error_action_has_distinct_code(self):
        action = AgentAction(
            type=AgentActionType.GIVE_UP,
            value="malformed provider output",
            stop_reason=AgentStopReason.PROVIDER_ERROR,
        )
        agent, _, _ = _agent(_browser(), [action])

        result = agent.complete_step(
            JourneyStep.FILL_SEARCH, "goal", verify=lambda: False, trigger="boom"
        )

        assert result.failure_code is FailureCode.LLM_ERROR
        assert result.stop_reason is AgentStopReason.PROVIDER_ERROR

    def test_model_coded_no_progress_uses_distinct_failure(self):
        action = AgentAction(
            type=AgentActionType.GIVE_UP,
            value="no controllable path advances the verified goal",
            stop_reason=AgentStopReason.NO_PROGRESS,
        )
        agent, _, _ = _agent(_browser(), [action])

        result = agent.complete_step(
            JourneyStep.FILL_SEARCH, "goal", verify=lambda: False, trigger="boom"
        )

        assert result.failure_code is FailureCode.AGENT_NO_PROGRESS

    def test_coded_budget_exhaustion_uses_distinct_failure(self):
        action = AgentAction(
            type=AgentActionType.GIVE_UP,
            value="daily allowance exhausted",
            stop_reason=AgentStopReason.BUDGET_EXHAUSTED,
        )
        agent, _, _ = _agent(_browser(), [action])

        result = agent.complete_step(
            JourneyStep.FILL_SEARCH, "goal", verify=lambda: False, trigger="boom"
        )

        assert result.failure_code is FailureCode.BUDGET_EXCEEDED
        assert result.stop_reason is AgentStopReason.BUDGET_EXHAUSTED

    def test_structured_history_reports_unchanged_action_outcome(self):
        browser = _browser()
        agent, brain, _ = _agent(browser, [_click(), _click()])

        agent.complete_step(
            JourneyStep.FILL_SEARCH,
            "goal",
            verify=lambda: False,
            trigger="boom",
            verification_condition="search results are visible",
        )

        second = brain.contexts[1]
        outcome = second.history[-1]
        assert outcome.outcome is AgentHistoryOutcome.EXECUTED
        assert not outcome.made_progress
        assert not outcome.goal_verified
        assert second.no_progress_count == 1
        assert second.verification_condition == "search results are visible"


class TestPopupOutcomes:
    def test_known_booking_popup_is_no_progress_and_visible_to_next_turn(self):
        browser = _browser()

        def _popup(b: FakeInteractiveBrowser, action: AgentAction) -> None:
            b.popup_count = 1
            b.popup_urls = ("https://www.booking.com/hotel/test.html",)

        browser.on_act = _popup
        agent, brain, _ = _agent(browser, [_click(), _click(), _click()])

        result = agent.complete_step(
            JourneyStep.OPEN_PROPERTY, "goal", verify=lambda: False, trigger="boom"
        )

        assert result.failure_code is FailureCode.AGENT_NO_PROGRESS
        assert brain.contexts[1].history[-1].popup_opened

    def test_uninspectable_popup_fails_closed(self):
        browser = _browser()

        def _popup(b: FakeInteractiveBrowser, action: AgentAction) -> None:
            b.popup_count = 1
            b.popup_urls = ()

        browser.on_act = _popup
        agent, brain, _ = _agent(browser, [_click(), _click()])

        result = agent.complete_step(
            JourneyStep.OPEN_PROPERTY, "goal", verify=lambda: False, trigger="boom"
        )

        assert result.failure_code is FailureCode.AGENT_GAVE_UP
        assert result.stop_reason is AgentStopReason.MISSING_BROWSER_CAPABILITY
        assert len(brain.decisions) == 1

    def test_external_popup_is_blocked(self):
        browser = _browser()

        def _popup(b: FakeInteractiveBrowser, action: AgentAction) -> None:
            b.popup_count = 1
            b.popup_urls = ("https://evil.example/phish",)

        browser.on_act = _popup
        agent, _, _ = _agent(browser, [_click()])

        result = agent.complete_step(
            JourneyStep.OPEN_PROPERTY, "goal", verify=lambda: False, trigger="boom"
        )

        assert result.failure_code is FailureCode.BLOCKED_ACTION
        assert result.stop_reason is AgentStopReason.UNSAFE_ACTION

    def test_external_same_tab_navigation_is_blocked(self):
        browser = _browser()

        def _navigate(b: FakeInteractiveBrowser, action: AgentAction) -> None:
            b.url = "https://evil.example/phish"

        browser.on_act = _navigate
        agent, _, _ = _agent(browser, [_click()])

        result = agent.complete_step(
            JourneyStep.OPEN_PROPERTY, "goal", verify=lambda: False, trigger="boom"
        )

        assert result.failure_code is FailureCode.BLOCKED_ACTION


class TestScreenshotTiers:
    def test_screenshot_first_on_entry(self):
        browser = _browser()
        done = {"ok": False}
        browser.on_act = lambda b, a: done.update(ok=True)
        agent, brain, _ = _agent(browser, [_click()])
        result = agent.complete_step(
            JourneyStep.FILL_SEARCH,
            "goal",
            verify=lambda: done["ok"],
            trigger="boom",
            screenshot_first=True,
        )
        assert result.ok
        assert result.used_screenshot
        assert brain.decisions[0].screenshot is not None

    def test_requested_screenshot_arrives_next_turn(self):
        browser = _browser()
        done = {"ok": False}
        browser.on_act = lambda b, a: done.update(ok=True)
        agent, brain, _ = _agent(
            browser,
            [AgentAction(type=AgentActionType.REQUEST_SCREENSHOT), _click()],
        )
        result = agent.complete_step(
            JourneyStep.FILL_SEARCH, "goal", verify=lambda: done["ok"], trigger="boom"
        )
        assert result.ok
        assert result.used_screenshot
        assert brain.decisions[0].screenshot is None  # tier 1 first
        assert brain.decisions[1].screenshot is not None  # tier 2 after request
        assert agent.last_screenshot is not None

    def test_screenshot_turn_costs_double_budget(self):
        browser = _browser()
        agent, brain, _ = _agent(
            browser,
            [AgentAction(type=AgentActionType.REQUEST_SCREENSHOT), _click(), _click()],
            settings=AgentSettings(max_steps=3),
        )
        result = agent.complete_step(
            JourneyStep.FILL_SEARCH, "goal", verify=lambda: False, trigger="boom"
        )
        # turn1 (1) + turn2 tier2 (2) = 3; turn3 would exceed max_steps=3
        assert result.failure_code is FailureCode.BUDGET_EXCEEDED

    def test_two_failed_actions_auto_escalate_to_tier2(self):
        browser = _browser()
        browser.fail_refs = {"e0"}
        agent, brain, _ = _agent(browser, [_click(), _click(), _click("e9")])
        agent.complete_step(
            JourneyStep.FILL_SEARCH, "goal", verify=lambda: False, trigger="boom"
        )
        # third decision (after 2 failures) sees a screenshot
        assert brain.decisions[2].screenshot is not None


class TestGuardInLoop:
    @pytest.mark.parametrize(
        ("page_text", "failure_code", "stop_reason"),
        [
            (
                "Enter your password to continue",
                FailureCode.AUTH_REQUIRED,
                AgentStopReason.AUTHENTICATION_REQUIRED,
            ),
            (
                "Verify you are human",
                FailureCode.BOT_WALL,
                AgentStopReason.CAPTCHA,
            ),
        ],
    )
    def test_auth_or_bot_wall_after_action_never_reaches_another_model_turn(
        self,
        page_text: str,
        failure_code: FailureCode,
        stop_reason: AgentStopReason,
    ) -> None:
        browser = _browser()
        browser.on_act = lambda current, _action: setattr(
            current, "page_text", page_text
        )
        agent, brain, _ = _agent(browser, [_click(), _click()])

        result = agent.complete_step(
            JourneyStep.READ_ROOM_TABLE,
            "goal",
            verify=lambda: False,
            trigger="boom",
        )

        assert result.failure_code is failure_code
        assert result.stop_reason is stop_reason
        assert len(brain.decisions) == 1
        assert len([item for item in browser.actions if item[0] == "act"]) == 1

    def test_unsafe_initial_page_prevents_verifier_and_provider(self):
        browser = _browser()
        browser.url = "https://evil.example/phish?token=private"
        verifier_calls = 0

        def _verify() -> bool:
            nonlocal verifier_calls
            verifier_calls += 1
            return True

        agent, brain, _ = _agent(browser, [_click()])

        result = agent.complete_step(
            JourneyStep.READ_ROOM_TABLE, "goal", verify=_verify, trigger="boom"
        )

        assert result.failure_code is FailureCode.BLOCKED_ACTION
        assert result.stop_reason is AgentStopReason.UNSAFE_ACTION
        assert verifier_calls == 0
        assert not brain.decisions
        assert not browser.actions

    def test_initial_checkout_page_prevents_verifier_and_provider(self):
        browser = _browser()
        browser.url = "https://secure.booking.com/checkout?token=private"
        verifier_calls = 0

        def _verify() -> bool:
            nonlocal verifier_calls
            verifier_calls += 1
            return True

        agent, brain, _ = _agent(browser, [_click()])

        result = agent.complete_step(
            JourneyStep.READ_ROOM_TABLE, "goal", verify=_verify, trigger="boom"
        )

        assert result.failure_code is FailureCode.BLOCKED_ACTION
        assert verifier_calls == 0
        assert not brain.decisions
        assert not browser.actions

    def test_verifier_cannot_turn_checkout_navigation_into_success(self):
        browser = _browser()

        def _verify() -> bool:
            browser.url = "https://secure.booking.com/checkout?token=private"
            return True

        agent, brain, _ = _agent(browser, [_click()])

        result = agent.complete_step(
            JourneyStep.READ_ROOM_TABLE, "goal", verify=_verify, trigger="boom"
        )

        assert result.failure_code is FailureCode.BLOCKED_ACTION
        assert result.stop_reason is AgentStopReason.UNSAFE_ACTION
        assert not brain.decisions
        assert not browser.actions

    def test_blocked_click_is_terminal(self):
        browser = _browser()
        agent, brain, _ = _agent(
            browser,
            [_click("e1"), AgentAction(type=AgentActionType.GIVE_UP, value="ok")],
        )
        result = agent.complete_step(
            JourneyStep.READ_ROOM_TABLE, "goal", verify=lambda: False, trigger="boom"
        )
        # the Book-now click never reached the browser
        assert not any("e1" in detail for kind, detail in browser.actions if kind == "act")
        assert result.failure_code is FailureCode.BLOCKED_ACTION
        assert len(brain.decisions) == 1

    def test_landing_on_blocked_url_fails_check(self):
        browser = _browser()
        done = {"ok": False}

        def _navigate(b: FakeInteractiveBrowser, action: AgentAction) -> None:
            b.url = "https://secure.booking.com/book.html?step=1"
            done["ok"] = True

        browser.on_act = _navigate
        agent, _, _ = _agent(browser, [_click()])
        result = agent.complete_step(
            JourneyStep.READ_ROOM_TABLE,
            "goal",
            verify=lambda: done["ok"],
            trigger="boom",
        )
        assert not result.ok
        assert result.failure_code is FailureCode.BLOCKED_ACTION


class TestBudgetsInLoop:
    def test_outer_budget_is_rechecked_after_provider_before_action(self):
        browser = _browser()
        brain = FakeAgentBrain([_click()])
        budget = AgentBudget(
            AgentSettings(check_timeout_seconds=60),
            clock=iter((0.0, 0.0, 61.0)).__next__,
        )
        agent = BrowserAgent(
            browser,
            brain,
            budget,
            TraceRecorder("b-1"),
            clock=lambda: 0.0,
        )

        result = agent.complete_step(
            JourneyStep.FILL_SEARCH, "goal", verify=lambda: False, trigger="boom"
        )

        assert result.failure_code is FailureCode.BUDGET_EXCEEDED
        assert len(brain.decisions) == 1
        assert not browser.actions

    def test_outer_budget_is_rechecked_after_browser_action(self):
        browser = _browser()
        brain = FakeAgentBrain([_click()])
        budget = AgentBudget(
            AgentSettings(check_timeout_seconds=60),
            clock=iter((0.0, 0.0, 0.0, 61.0)).__next__,
        )
        agent = BrowserAgent(
            browser,
            brain,
            budget,
            TraceRecorder("b-1"),
            clock=lambda: 0.0,
        )

        result = agent.complete_step(
            JourneyStep.FILL_SEARCH, "goal", verify=lambda: False, trigger="boom"
        )

        assert result.failure_code is FailureCode.BUDGET_EXCEEDED
        assert len([item for item in browser.actions if item[0] == "act"]) == 1

    def test_local_recovery_timeout_is_distinct_budget_stop(self):
        browser = _browser()
        brain = FakeAgentBrain([_click()])
        agent = BrowserAgent(
            browser,
            brain,
            AgentBudget(AgentSettings()),
            TraceRecorder("b-1"),
            recovery_policy=RecoveryPolicy(timeout_seconds=60),
            clock=iter((0.0, 61.0)).__next__,
        )

        result = agent.complete_step(
            JourneyStep.FILL_SEARCH, "goal", verify=lambda: False, trigger="boom"
        )

        assert result.failure_code is FailureCode.BUDGET_EXCEEDED
        assert result.stop_reason is AgentStopReason.BUDGET_EXHAUSTED
        assert not brain.decisions

    def test_late_provider_response_cannot_trigger_browser_action(self):
        browser = _browser()
        brain = FakeAgentBrain([_click()])
        agent = BrowserAgent(
            browser,
            brain,
            AgentBudget(AgentSettings()),
            TraceRecorder("b-1"),
            recovery_policy=RecoveryPolicy(timeout_seconds=60),
            clock=iter((0.0, 0.0, 61.0)).__next__,
        )

        result = agent.complete_step(
            JourneyStep.FILL_SEARCH, "goal", verify=lambda: False, trigger="boom"
        )

        assert result.failure_code is FailureCode.BUDGET_EXCEEDED
        assert result.stop_reason is AgentStopReason.BUDGET_EXHAUSTED
        assert len(brain.decisions) == 1
        assert not browser.actions

    def test_step_cap_breach_returns_budget_exceeded(self):
        agent, _, _ = _agent(
            _browser(), [_click()] * 5, settings=AgentSettings(max_steps=2)
        )
        result = agent.complete_step(
            JourneyStep.FILL_SEARCH, "goal", verify=lambda: False, trigger="boom"
        )
        assert result.failure_code is FailureCode.BUDGET_EXCEEDED

    def test_llm_call_cap_breach_returns_budget_exceeded(self):
        agent, _, _ = _agent(
            _browser(), [_click()] * 5, settings=AgentSettings(max_llm_calls=2)
        )
        result = agent.complete_step(
            JourneyStep.FILL_SEARCH, "goal", verify=lambda: False, trigger="boom"
        )
        assert result.failure_code is FailureCode.BUDGET_EXCEEDED
