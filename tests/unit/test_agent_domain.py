import pytest

from booksaver.domain.agent import (
    AgentAction,
    AgentActionType,
    AgentSettings,
    ElementInfo,
    Observation,
    blocked_action_reason,
    blocked_url_reason,
)


def _obs(elements: tuple[ElementInfo, ...] = ()) -> Observation:
    return Observation(url="https://www.booking.com", title="t", text="", elements=elements)


class TestAgentSettings:
    def test_job_cost_cap_defaults_to_one_dollar_and_is_bounded(self):
        assert AgentSettings().max_job_cost_micro_usd == 1_000_000
        for invalid in (0, 1_000_001):
            with pytest.raises(ValueError, match="max_job_cost_usd"):
                AgentSettings(max_job_cost_micro_usd=invalid)


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

    def test_external_link_blocked_before_browser_action(self):
        obs = _obs(
            (
                ElementInfo(
                    ref="e0",
                    role="link",
                    label="Trip details",
                    href="https://example.test/collect?token=private",
                ),
            )
        )
        assert blocked_action_reason(self._click(), obs) is not None

    @pytest.mark.parametrize(
        "label",
        ["Modify reservation", "Change dates", "Update payment", "Save changes"],
    )
    def test_additional_mutation_labels_are_blocked(self, label: str):
        obs = _obs((ElementInfo(ref="e0", role="button", label=label),))
        assert blocked_action_reason(self._click(), obs) is not None

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
        assert blocked_url_reason("https://secure.booking.com/orders/create")
        assert blocked_url_reason("https://www.booking.com/account/settings")

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
