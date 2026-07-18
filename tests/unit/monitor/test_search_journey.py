from __future__ import annotations

from urllib.parse import parse_qs, urlparse

from booksaver.domain.check_result import FailureCode
from booksaver.domain.journey import JourneyStep
from booksaver.domain.session import SessionMode
from booksaver.monitor.search_journey import SearchJourney

from .fakes import FakeInteractiveBrowser, make_booking

_PROPERTY_URL = (
    "https://www.booking.com/hotel/test.html"
    "?checkin=2026-09-01&checkout=2026-09-05&group_adults=2"
)
_ACTIVE_STEPS = [
    JourneyStep.SUBMIT_SEARCH,
    JourneyStep.LOCATE_PROPERTY,
    JourneyStep.OPEN_PROPERTY,
    JourneyStep.VERIFY_CONTEXT,
    JourneyStep.READ_ROOM_TABLE,
]


def _happy_browser(**overrides) -> FakeInteractiveBrowser:
    browser = FakeInteractiveBrowser(
        titles=["Some Other Hotel", "Hotel Test"],
        page_text="Standard Double\n€ 350.00\nFree cancellation",
        **overrides,
    )
    browser.property_url = _PROPERTY_URL
    return browser


class TestHappyPath:
    def test_all_active_steps_succeed(self):
        result = SearchJourney(_happy_browser()).run(make_booking())

        assert result.ok
        assert [outcome.step for outcome in result.outcomes] == _ACTIVE_STEPS
        assert all(outcome.ok for outcome in result.outcomes)

    def test_first_navigation_is_exact_results_query(self):
        browser = _happy_browser()

        SearchJourney(browser).run(make_booking())

        first_url = next(value for kind, value in browser.actions if kind == "goto")
        parsed = urlparse(first_url)
        query = parse_qs(parsed.query)
        assert parsed.path == "/searchresults.html"
        assert query == {
            "ss": ["Hotel Test"],
            "checkin": ["2026-09-01"],
            "checkout": ["2026-09-05"],
            "group_adults": ["2"],
            "group_children": ["0"],
            "no_rooms": ["1"],
            "sb": ["1"],
            "src": ["searchresults"],
        }

    def test_homepage_form_is_never_operated(self):
        browser = _happy_browser(
            fail_selectors={
                'input[name="ss"]',
                "searchbox-datepicker",
                "occupancy-config",
                'button[type="submit"]',
            }
        )

        result = SearchJourney(browser).run(make_booking())

        assert result.ok
        assert not [action for action in browser.actions if action[0] in {"fill", "click", "press"}]

    def test_property_matched_by_normalised_name(self):
        browser = _happy_browser()
        browser.titles = ["HOTEL TEST!"]

        result = SearchJourney(browser).run(make_booking())

        assert result.ok


class TestStepFailures:
    def test_results_navigation_failure_is_navigation_error(self):
        result = SearchJourney(_happy_browser(fail_goto=True)).run(make_booking())

        assert not result.ok
        assert result.failure_code is FailureCode.NAVIGATION_ERROR
        assert result.failed_step.step is JourneyStep.SUBMIT_SEARCH

    def test_property_absent_from_results_is_property_not_found(self):
        browser = _happy_browser()
        browser.titles = ["Wrong Hotel", "Another Wrong Hotel"]

        result = SearchJourney(browser).run(make_booking())

        assert result.failure_code is FailureCode.PROPERTY_NOT_FOUND
        assert result.failed_step.step is JourneyStep.LOCATE_PROPERTY
        assert "Hotel Test" in result.failed_step.detail

    def test_wrong_dates_on_property_page_fail_verify_context(self):
        browser = _happy_browser()
        browser.property_url = (
            "https://www.booking.com/hotel/test.html"
            "?checkin=2026-09-02&checkout=2026-09-05&group_adults=2"
        )

        result = SearchJourney(browser).run(make_booking())

        assert result.failure_code is FailureCode.STEP_FAILED
        assert result.failed_step.step is JourneyStep.VERIFY_CONTEXT

    def test_wrong_occupancy_on_property_page_fails_verify_context(self):
        browser = _happy_browser()
        browser.property_url = (
            "https://www.booking.com/hotel/test.html"
            "?checkin=2026-09-01&checkout=2026-09-05&group_adults=4"
        )

        result = SearchJourney(browser).run(make_booking())

        assert result.failure_code is FailureCode.STEP_FAILED
        assert result.failed_step.step is JourneyStep.VERIFY_CONTEXT


class TestWallDetection:
    def test_captcha_on_results_page_is_bot_wall(self):
        browser = _happy_browser()
        browser.page_text = "Please verify you are human to continue"

        result = SearchJourney(browser).run(make_booking())

        assert result.failure_code is FailureCode.BOT_WALL
        assert result.failed_step.step is JourneyStep.SUBMIT_SEARCH

    def test_signed_out_page_classified_as_auth_required(self):
        browser = _happy_browser(fail_selectors={"property-card"})
        browser.page_text = "Log in to your account to continue"

        result = SearchJourney(browser).run(make_booking())

        assert result.failure_code is FailureCode.AUTH_REQUIRED

    def test_captcha_takes_priority_over_step_code(self):
        browser = _happy_browser(fail_selectors={"property-card"})
        browser.page_text = "unusual traffic detected - hcaptcha"

        result = SearchJourney(browser).run(make_booking())

        assert result.failure_code is FailureCode.BOT_WALL

    def test_signed_out_page_is_not_auth_failure_when_logged_out(self):
        browser = _happy_browser(fail_selectors={"property-card"})
        browser.page_text = "Log in to your account to continue"

        result = SearchJourney(browser, session_mode=SessionMode.LOGGED_OUT).run(
            make_booking()
        )

        assert result.failure_code is not FailureCode.AUTH_REQUIRED

    def test_captcha_still_wins_when_logged_out(self):
        browser = _happy_browser(fail_selectors={"property-card"})
        browser.page_text = "unusual traffic detected - hcaptcha"

        result = SearchJourney(browser, session_mode=SessionMode.LOGGED_OUT).run(
            make_booking()
        )

        assert result.failure_code is FailureCode.BOT_WALL
