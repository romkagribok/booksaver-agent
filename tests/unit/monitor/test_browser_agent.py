from __future__ import annotations

from booksaver.domain.agent import (
    AgentAction,
    AgentActionType,
    AgentBudget,
    AgentSettings,
    ElementInfo,
)
from booksaver.domain.check_result import FailureCode
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
    def test_blocked_click_is_refused_and_loop_continues(self):
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
        assert result.failure_code is FailureCode.AGENT_GAVE_UP

    def test_landing_on_blocked_url_fails_check(self):
        browser = _browser()

        def _navigate(b: FakeInteractiveBrowser, action: AgentAction) -> None:
            b.url = "https://secure.booking.com/book.html?step=1"

        browser.on_act = _navigate
        agent, _, _ = _agent(browser, [_click()])
        result = agent.complete_step(
            JourneyStep.READ_ROOM_TABLE, "goal", verify=lambda: True, trigger="boom"
        )
        assert not result.ok
        assert result.failure_code is FailureCode.BLOCKED_ACTION


class TestBudgetsInLoop:
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
