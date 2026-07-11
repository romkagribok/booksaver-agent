from __future__ import annotations

from booksaver.domain.check_result import FailureCode
from booksaver.domain.journey import JourneyStep
from booksaver.domain.session import SessionMode
from booksaver.monitor.search_journey import SearchJourney

from .fakes import FakeInteractiveBrowser, make_booking

_PROPERTY_URL = (
    "https://www.booking.com/hotel/test.html"
    "?checkin=2026-09-01&checkout=2026-09-05&group_adults=2"
)


def _happy_browser(**overrides) -> FakeInteractiveBrowser:
    browser = FakeInteractiveBrowser(
        titles=["Some Other Hotel", "Hotel Test"],
        page_text="Standard Double\n€ 350.00\nFree cancellation",
        **overrides,
    )
    browser.property_url = _PROPERTY_URL
    return browser


class TestHappyPath:
    def test_all_steps_succeed(self):
        journey = SearchJourney(_happy_browser())
        result = journey.run(make_booking())
        assert result.ok
        assert [o.step for o in result.outcomes] == list(JourneyStep)
        assert all(o.ok for o in result.outcomes)

    def test_property_matched_by_normalised_name(self):
        browser = _happy_browser()
        browser.titles = ["HOTEL TEST!"]  # punctuation/case differences still match
        result = SearchJourney(browser).run(make_booking())
        assert result.ok

    def test_search_uses_property_name_and_dates(self):
        browser = _happy_browser()
        SearchJourney(browser).run(make_booking())
        fills = [a for kind, a in browser.actions if kind == "fill"]
        assert any("Hotel Test" in f for f in fills)
        clicks = [a for kind, a in browser.actions if kind == "click"]
        assert any('data-date="2026-09-01"' in c for c in clicks)
        assert any('data-date="2026-09-05"' in c for c in clicks)


class TestStepFailures:
    def test_home_page_unreachable_is_navigation_error(self):
        browser = _happy_browser(fail_goto=True)
        result = SearchJourney(browser).run(make_booking())
        assert not result.ok
        assert result.failure_code is FailureCode.NAVIGATION_ERROR
        assert result.failed_step.step is JourneyStep.OPEN_HOME

    def test_missing_search_box_fails_fill_search_step(self):
        browser = _happy_browser(fail_selectors={'input[name="ss"]'})
        result = SearchJourney(browser).run(make_booking())
        assert not result.ok
        # open_home waits for the search box, so the drift surfaces there
        assert result.failed_step.step is JourneyStep.OPEN_HOME

    def test_missing_date_cell_is_step_failed(self):
        browser = FakeInteractiveBrowser(fail_selectors={"data-date"})
        result = SearchJourney(browser).run(make_booking())
        assert result.failure_code.value == "step_failed"
        assert result.failed_step.step is JourneyStep.FILL_SEARCH

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

    def test_wrong_occupancy_in_url_fails_verify_context(self):
        browser = _happy_browser()
        browser.property_url = (
            "https://www.booking.com/hotel/test.html"
            "?checkin=2026-09-01&checkout=2026-09-05&group_adults=4"
        )
        result = SearchJourney(browser).run(make_booking())
        assert result.failed_step.step is JourneyStep.VERIFY_CONTEXT


class TestWallDetection:
    def test_captcha_on_home_page_is_bot_wall(self):
        browser = _happy_browser()
        browser.page_text = "Please verify you are human to continue"
        result = SearchJourney(browser).run(make_booking())
        assert result.failure_code is FailureCode.BOT_WALL
        assert result.failed_step.step is JourneyStep.DISMISS_OVERLAYS

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

    def test_signed_out_page_never_classified_as_auth_required_when_logged_out(self):
        # US-035/FR-8: AUTH_REQUIRED presupposes a session that dropped. With no
        # session at all, a "sign in" banner is just the anonymous journey and
        # must fall through to the step-specific failure code instead.
        browser = _happy_browser(fail_selectors={"property-card"})
        browser.page_text = "Log in to your account to continue"
        result = SearchJourney(browser, session_mode=SessionMode.LOGGED_OUT).run(
            make_booking()
        )
        assert result.failure_code is not FailureCode.AUTH_REQUIRED

    def test_captcha_still_wins_over_step_code_when_logged_out(self):
        browser = _happy_browser(fail_selectors={"property-card"})
        browser.page_text = "unusual traffic detected - hcaptcha"
        result = SearchJourney(browser, session_mode=SessionMode.LOGGED_OUT).run(
            make_booking()
        )
        assert result.failure_code is FailureCode.BOT_WALL


class TestOverlays:
    def test_present_consent_banner_is_clicked(self):
        browser = _happy_browser(present_selectors={"#onetrust-accept-btn-handler"})
        result = SearchJourney(browser).run(make_booking())
        assert result.ok
        clicks = [a for kind, a in browser.actions if kind == "click"]
        assert "#onetrust-accept-btn-handler" in clicks

    def test_absent_overlays_do_not_fail_the_step(self):
        result = SearchJourney(_happy_browser()).run(make_booking())
        overlay = next(
            o for o in result.outcomes if o.step is JourneyStep.DISMISS_OVERLAYS
        )
        assert overlay.ok
