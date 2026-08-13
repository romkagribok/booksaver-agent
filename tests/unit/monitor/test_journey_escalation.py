from __future__ import annotations

from booksaver.domain.agent import (
    AgentAction,
    AgentActionType,
    AgentBudget,
    AgentSettings,
    AgentStopReason,
    ElementInfo,
    EscalationResult,
)
from booksaver.domain.browser_resilience import (
    DiagnosisProvenance,
    DomStepId,
    OperatorAction,
    TerminalBrowserDiagnosis,
    TerminalBrowserReason,
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
    def test_successful_model_recovery_preserves_positive_diagnosis(self):
        browser = _happy_browser(fail_selectors={"property-card"})
        diagnosis = TerminalBrowserDiagnosis(
            reason=TerminalBrowserReason.POSTCONDITION_SATISFIED,
            step_id=DomStepId.PRICE_SEARCH_QUERY_SUBMISSION,
            provenance=DiagnosisProvenance.SONNET_RECOVERED,
            confidence=0.92,
            evidence=frozenset(),
            operator_action=OperatorAction.NONE,
        )

        class RecoveringEscalator:
            def complete_step(self, *args, **kwargs):
                browser.fail_selectors.clear()
                browser.present_selectors.add('[data-testid="property-card"]')
                return EscalationResult(
                    ok=True,
                    detail="recovered changed search results",
                    diagnosis=diagnosis,
                )

        result = SearchJourney(
            browser,
            escalator=RecoveringEscalator(),  # type: ignore[arg-type]
        ).run(make_booking())

        assert result.ok
        assert result.assisted_diagnoses == (diagnosis,)

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
        assert result.failure_code is FailureCode.DOM_AMBIGUITY
        assert result.failed_step.step is JourneyStep.SUBMIT_SEARCH

    def test_model_auth_diagnosis_maps_exactly_when_changed_dom_hides_login_text(self):
        browser = _happy_browser(fail_selectors={"property-card"})
        journey = _journey_with_agent(
            browser,
            [
                AgentAction(
                    type=AgentActionType.GIVE_UP,
                    value="protected authentication page",
                    stop_reason=AgentStopReason.AUTHENTICATION_REQUIRED,
                )
            ],
        )

        result = journey.run(make_booking())

        assert result.failure_code is FailureCode.AUTH_REQUIRED
        assert result.agent_assisted

    def test_model_captcha_diagnosis_maps_exactly_when_changed_dom_hides_markers(self):
        browser = _happy_browser(fail_selectors={"property-card"})
        journey = _journey_with_agent(
            browser,
            [
                AgentAction(
                    type=AgentActionType.GIVE_UP,
                    value="protected challenge page",
                    stop_reason=AgentStopReason.CAPTCHA,
                )
            ],
        )

        result = journey.run(make_booking())

        assert result.failure_code is FailureCode.BOT_WALL
        assert result.agent_assisted

    def test_budget_breach_during_results_recovery_is_terminal(self):
        browser = _happy_browser(fail_selectors={"property-card"})
        journey = _journey_with_agent(
            browser,
            [AgentAction(type=AgentActionType.CLICK, ref="e0")] * 10,
            settings=AgentSettings(max_steps=2),
        )

        result = journey.run(make_booking())

        assert result.failure_code is FailureCode.JOB_COST_LIMIT
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

    def test_agent_recovers_semantic_room_content_with_screenshot_first(self):
        browser = _happy_browser(fail_selectors={"hprt-table", "rt-room-table"})
        browser.page_text = "Check available dates"

        def _remove_anchors(b: FakeInteractiveBrowser, url: str) -> None:
            if "/hotel/" in url:
                b.present_selectors.difference_update(
                    {"#hprt-table", '[data-testid="rt-room-table"]'}
                )

        def _reveal_rates(b: FakeInteractiveBrowser, action: AgentAction) -> None:
            b.page_text = "Standard Double\n€ 350.00\nFree cancellation"

        browser.on_goto = _remove_anchors
        browser.on_act = _reveal_rates
        journey = _journey_with_agent(
            browser, [AgentAction(type=AgentActionType.CLICK, ref="e0")]
        )

        result = journey.run(make_booking())

        assert result.ok
        assert result.agent_assisted
        assert ("screenshot", "") in browser.actions
        read = next(
            outcome
            for outcome in result.outcomes
            if outcome.step is JourneyStep.READ_ROOM_TABLE
        )
        assert "agent completed" in read.detail

    def test_agent_revealed_no_availability_is_classified_without_more_recovery(self):
        browser = _happy_browser(fail_selectors={"hprt-table", "rt-room-table"})
        browser.page_text = "Check available dates"

        def _remove_anchors(b: FakeInteractiveBrowser, url: str) -> None:
            if "/hotel/" in url:
                b.present_selectors.difference_update(
                    {"#hprt-table", '[data-testid="rt-room-table"]'}
                )

        def _reveal_unavailable(b: FakeInteractiveBrowser, action: AgentAction) -> None:
            b.page_text = "This property is not available for your dates"

        browser.on_goto = _remove_anchors
        browser.on_act = _reveal_unavailable
        journey = _journey_with_agent(
            browser,
            [
                AgentAction(type=AgentActionType.CLICK, ref="e0"),
                AgentAction(type=AgentActionType.GIVE_UP, value="no availability"),
            ],
        )

        result = journey.run(make_booking())

        assert result.failure_code is FailureCode.NO_EQUIVALENT_OFFER
        assert result.failed_step.step is JourneyStep.READ_ROOM_TABLE
