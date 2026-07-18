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
from booksaver.monitor.search_journey import SearchJourney
from booksaver.monitor.trace import TraceRecorder

from .fakes import FakeAgentBrain, FakeInteractiveBrowser, make_booking

_PROPERTY_URL = (
    "https://www.booking.com/hotel/test.html"
    "?checkin=2026-09-01&checkout=2026-09-05&group_adults=2"
)


def _happy_browser(**overrides) -> FakeInteractiveBrowser:
    browser = FakeInteractiveBrowser(
        titles=["Hotel Test"],
        page_text="Standard Double\n€ 350.00\nFree cancellation",
        **overrides,
    )
    browser.property_url = _PROPERTY_URL
    browser.elements = (ElementInfo(ref="e0", role="button", label="Show results"),)
    return browser


def _journey_with_agent(
    browser: FakeInteractiveBrowser,
    script: list[AgentAction],
    settings: AgentSettings | None = None,
) -> SearchJourney:
    recorder = TraceRecorder("b-1")
    budget = AgentBudget(settings or AgentSettings())
    escalator = BrowserAgent(browser, FakeAgentBrain(script), budget, recorder)
    return SearchJourney(
        browser, escalator=escalator, recorder=recorder, checkpoint=budget.check_time
    )


class TestEscalationInJourney:
    def test_agent_recovers_results_layout_and_journey_continues(self):
        browser = _happy_browser(fail_selectors={"property-card"})

        def _fix(b: FakeInteractiveBrowser, action: AgentAction) -> None:
            b.fail_selectors.clear()
            b.present_selectors.add('[data-testid="property-card"]')

        browser.on_act = _fix
        journey = _journey_with_agent(
            browser, [AgentAction(type=AgentActionType.CLICK, ref="e0")]
        )

        result = journey.run(make_booking())

        assert result.ok
        assert result.agent_assisted
        submit = next(
            outcome
            for outcome in result.outcomes
            if outcome.step is JourneyStep.SUBMIT_SEARCH
        )
        assert submit.ok
        assert "agent completed" in submit.detail

    def test_agent_give_up_at_results_step_is_terminal(self):
        browser = _happy_browser(fail_selectors={"property-card"})
        journey = _journey_with_agent(
            browser, [AgentAction(type=AgentActionType.GIVE_UP, value="hopeless")]
        )

        result = journey.run(make_booking())

        assert not result.ok
        assert result.failure_code is FailureCode.AGENT_GAVE_UP
        assert result.failed_step.step is JourneyStep.SUBMIT_SEARCH

    def test_budget_breach_during_results_recovery_is_terminal(self):
        browser = _happy_browser(fail_selectors={"property-card"})
        journey = _journey_with_agent(
            browser,
            [AgentAction(type=AgentActionType.CLICK, ref="e0")] * 10,
            settings=AgentSettings(max_steps=2),
        )

        result = journey.run(make_booking())

        assert result.failure_code is FailureCode.BUDGET_EXCEEDED
        assert result.failed_step.step is JourneyStep.SUBMIT_SEARCH

    def test_bot_wall_is_never_escalated(self):
        browser = _happy_browser()
        browser.page_text = "please verify you are human - hcaptcha"
        script = [AgentAction(type=AgentActionType.CLICK, ref="e0")]
        journey = _journey_with_agent(browser, script)

        result = journey.run(make_booking())

        assert result.failure_code is FailureCode.BOT_WALL
        assert not result.agent_assisted
        assert script

    def test_scripted_only_run_is_not_agent_assisted(self):
        result = _journey_with_agent(_happy_browser(), []).run(make_booking())

        assert result.ok
        assert not result.agent_assisted
