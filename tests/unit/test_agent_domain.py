import pytest

from booksaver.domain.agent import (
    AgentAction,
    AgentActionType,
    AgentBudget,
    AgentSettings,
    BudgetExceeded,
    ElementInfo,
    Observation,
    blocked_action_reason,
    blocked_url_reason,
)


def _obs(elements: tuple[ElementInfo, ...] = ()) -> Observation:
    return Observation(url="https://www.booking.com", title="t", text="", elements=elements)


class TestAgentSettings:
    def test_defaults(self):
        s = AgentSettings()
        assert (s.max_steps, s.max_llm_calls, s.check_timeout_seconds) == (15, 20, 180)

    def test_invalid_steps_rejected(self):
        with pytest.raises(ValueError, match="max_steps"):
            AgentSettings(max_steps=0)

    def test_invalid_llm_calls_rejected(self):
        with pytest.raises(ValueError, match="max_llm_calls"):
            AgentSettings(max_llm_calls=0)

    def test_timeout_bounds(self):
        with pytest.raises(ValueError, match="check_timeout_seconds"):
            AgentSettings(check_timeout_seconds=10)
        with pytest.raises(ValueError, match="check_timeout_seconds"):
            AgentSettings(check_timeout_seconds=7200)


class TestAgentBudget:
    def test_steps_cap(self):
        budget = AgentBudget(AgentSettings(max_steps=2))
        budget.consume_step()
        budget.consume_step()
        with pytest.raises(BudgetExceeded, match="step cap"):
            budget.consume_step()

    def test_screenshot_turn_counts_double(self):
        budget = AgentBudget(AgentSettings(max_steps=2))
        with pytest.raises(BudgetExceeded):
            budget.consume_step(tier2=True)
            budget.consume_step(tier2=True)
        assert budget.steps_used >= 3

    def test_llm_call_cap(self):
        budget = AgentBudget(AgentSettings(max_llm_calls=1))
        budget.consume_llm_call()
        with pytest.raises(BudgetExceeded, match="LLM call cap"):
            budget.consume_llm_call()

    def test_wall_clock_with_injected_clock(self):
        now = [0.0]
        budget = AgentBudget(
            AgentSettings(check_timeout_seconds=60), clock=lambda: now[0]
        )
        budget.check_time()  # fine at t=0
        now[0] = 61.0
        with pytest.raises(BudgetExceeded, match="timeout"):
            budget.check_time()


class TestActionGuard:
    def _click(self, ref: str = "e0") -> AgentAction:
        return AgentAction(type=AgentActionType.CLICK, ref=ref)

    def test_reserve_button_blocked(self):
        obs = _obs((ElementInfo(ref="e0", role="button", label="I'll reserve"),))
        assert blocked_action_reason(self._click(), obs) is not None

    def test_book_now_blocked(self):
        obs = _obs((ElementInfo(ref="e0", role="button", label="Book now"),))
        assert blocked_action_reason(self._click(), obs) is not None

    def test_cancel_booking_blocked(self):
        obs = _obs((ElementInfo(ref="e0", role="link", label="Cancel booking",
                                href="/myreservations"),))
        assert blocked_action_reason(self._click(), obs) is not None

    def test_checkout_href_blocked(self):
        obs = _obs((ElementInfo(ref="e0", role="link", label="Continue",
                                href="https://secure.booking.com/book.html?x=1"),))
        assert blocked_action_reason(self._click(), obs) is not None

    def test_room_link_allowed(self):
        obs = _obs((ElementInfo(ref="e0", role="link", label="Standard Double Room",
                                href="/hotel/test.html#room1"),))
        assert blocked_action_reason(self._click(), obs) is None

    def test_cancellation_policy_text_allowed(self):
        # Reading policy wording is fine; only mutating targets are blocked
        obs = _obs((ElementInfo(ref="e0", role="button", label="Show cancellation policy"),))
        assert blocked_action_reason(self._click(), obs) is None

    def test_scroll_never_blocked(self):
        action = AgentAction(type=AgentActionType.SCROLL, value="down")
        obs = _obs((ElementInfo(ref="e0", role="button", label="Book now"),))
        assert blocked_action_reason(action, obs) is None

    def test_unknown_ref_is_not_a_guard_matter(self):
        assert blocked_action_reason(self._click("e99"), _obs()) is None

    def test_blocked_urls(self):
        assert blocked_url_reason("https://secure.booking.com/book.html?stage=1")
        assert blocked_url_reason("https://www.booking.com/cancel/12345")
        assert blocked_url_reason("https://payments.booking.com/session")
        assert blocked_url_reason("https://www.booking.com/checkout/start")

    def test_normal_urls_allowed(self):
        assert blocked_url_reason("https://www.booking.com/hotel/test.html") is None
        assert blocked_url_reason("https://www.booking.com/searchresults.html") is None


class TestObservationDescribe:
    def test_describe_lists_elements_and_text(self):
        obs = Observation(
            url="https://x",
            title="Hotel",
            text="Room prices here",
            elements=(ElementInfo(ref="e0", role="button", label="Search"),),
        )
        rendered = obs.describe()
        assert "[e0] button: 'Search'" in rendered
        assert "Room prices here" in rendered

    def test_describe_bounds_text(self):
        obs = Observation(url="u", title="t", text="x" * 100, elements=())
        assert len(obs.describe(max_text_chars=10)) < 100
