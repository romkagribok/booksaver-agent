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
    browser.elements = (ElementInfo(ref="e0", role="button", label="Accept dates"),)
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
    def test_agent_completes_failed_step_and_journey_continues(self):
        browser = _happy_browser(fail_selectors={"data-date"})  # FILL_SEARCH breaks

        def _fix(b: FakeInteractiveBrowser, action: AgentAction) -> None:
            b.fail_selectors.clear()  # agent "closed the datepicker overlay"

        browser.on_act = _fix
        journey = _journey_with_agent(
            browser, [AgentAction(type=AgentActionType.CLICK, ref="e0")]
        )
        result = journey.run(make_booking())
        assert result.ok
        assert result.agent_assisted
        fill = next(o for o in result.outcomes if o.step is JourneyStep.FILL_SEARCH)
        assert fill.ok
        assert "agent completed" in fill.detail

    def test_agent_give_up_fails_check_with_agent_gave_up(self):
        browser = _happy_browser(fail_selectors={"data-date"})
        journey = _journey_with_agent(
            browser, [AgentAction(type=AgentActionType.GIVE_UP, value="hopeless")]
        )
        result = journey.run(make_booking())
        assert not result.ok
        assert result.failure_code is FailureCode.AGENT_GAVE_UP
        assert result.agent_assisted

    def test_budget_breach_during_escalation_maps_to_budget_exceeded(self):
        # SUBMIT_SEARCH has a real postcondition (property cards visible) that the
        # agent's clicks never satisfy, so the loop runs until the step cap trips.
        browser = _happy_browser(fail_selectors={"property-card"})
        journey = _journey_with_agent(
            browser,
            [AgentAction(type=AgentActionType.CLICK, ref="e0")] * 10,
            settings=AgentSettings(max_steps=2),
        )
        result = journey.run(make_booking())
        assert result.failure_code is FailureCode.BUDGET_EXCEEDED

    def test_bot_wall_is_never_escalated(self):
        browser = _happy_browser()
        browser.page_text = "please verify you are human - hcaptcha"
        script = [AgentAction(type=AgentActionType.CLICK, ref="e0")]
        journey = _journey_with_agent(browser, script)
        result = journey.run(make_booking())
        assert result.failure_code is FailureCode.BOT_WALL
        assert not result.agent_assisted
        assert script  # brain was never consulted

    def test_scripted_only_run_is_not_agent_assisted(self):
        journey = _journey_with_agent(_happy_browser(), [])
        result = journey.run(make_booking())
        assert result.ok
        assert not result.agent_assisted
