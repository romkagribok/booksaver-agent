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
            "selected_currency": ["EUR"],
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

    def test_fresh_property_href_receives_complete_trusted_context(self):
        browser = _happy_browser()
        browser.property_url = (
            "https://www.booking.com/hotel/test.html?aid=304142&checkin=2020-01-01"
            "&group_adults=9"
            "&selected_currency=USD"
        )

        result = SearchJourney(browser).run(make_booking())

        assert result.ok
        property_url = [value for kind, value in browser.actions if kind == "goto"][1]
        query = parse_qs(urlparse(property_url).query)
        assert query["aid"] == ["304142"]
        assert query["checkin"] == ["2026-09-01"]
        assert query["checkout"] == ["2026-09-05"]
        assert query["group_adults"] == ["2"]
        assert query["group_children"] == ["0"]
        assert query["no_rooms"] == ["1"]
        assert query["selected_currency"] == ["EUR"]

    def test_fresh_property_href_preserves_duplicate_non_context_parameters(self):
        browser = _happy_browser()
        browser.property_url = (
            "https://www.booking.com/hotel/test.html?label=one&label=two"
            "&checkin=2020-01-01"
        )

        result = SearchJourney(browser).run(make_booking())

        assert result.ok
        property_url = [value for kind, value in browser.actions if kind == "goto"][1]
        query = parse_qs(urlparse(property_url).query)
        assert query["label"] == ["one", "two"]
        assert query["checkin"] == ["2026-09-01"]

    def test_deterministic_currency_control_selects_and_verifies_baseline(self):
        browser = _happy_browser(currency_label="USD")
        journey = SearchJourney(browser)

        detail = journey.align_currency(make_booking())

        assert browser.currency_label == "EUR"
        assert "requested=EUR" in detail
        assert "header preference verified" in detail

    def test_currency_control_must_confirm_requested_currency(self):
        browser = _happy_browser(currency_label="USD")

        def _ignore_currency_click(b: FakeInteractiveBrowser, selector: str) -> None:
            if ':has-text("EUR")' in selector:
                b.currency_label = "USD"

        original_click = browser.click

        def click(selector: str) -> None:
            original_click(selector)
            _ignore_currency_click(browser, selector)

        browser.click = click  # type: ignore[method-assign]

        try:
            SearchJourney(browser).align_currency(make_booking())
        except RuntimeError as exc:
            assert "did not confirm EUR" in str(exc)
        else:
            raise AssertionError("unverified currency preference must fail")

    def test_consent_panel_is_declined_after_navigation(self):
        selector = 'button:text-is("Decline")'
        browser = _happy_browser(present_selectors={selector})

        result = SearchJourney(browser).run(make_booking())

        assert result.ok
        assert ("click", selector) in browser.actions

    def test_semantic_rate_content_does_not_require_legacy_anchor(self):
        browser = _happy_browser(fail_selectors={"hprt-table", "rt-room-table"})

        def _remove_anchors(b: FakeInteractiveBrowser, url: str) -> None:
            if "/hotel/" in url:
                b.present_selectors.difference_update(
                    {"#hprt-table", '[data-testid="rt-room-table"]'}
                )

        browser.on_goto = _remove_anchors

        result = SearchJourney(browser).run(make_booking())

        assert result.ok
        read = next(
            outcome
            for outcome in result.outcomes
            if outcome.step is JourneyStep.READ_ROOM_TABLE
        )
        assert "semantic room/rate content" in read.detail


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
        browser.property_redirect_url = (
            "https://www.booking.com/hotel/test.html"
            "?checkin=2026-09-02&checkout=2026-09-05&group_adults=2"
            "&group_children=0&no_rooms=1"
        )

        result = SearchJourney(browser).run(make_booking())

        assert result.failure_code is FailureCode.STEP_FAILED
        assert result.failed_step.step is JourneyStep.VERIFY_CONTEXT

    def test_wrong_occupancy_on_property_page_fails_verify_context(self):
        browser = _happy_browser()
        browser.property_redirect_url = (
            "https://www.booking.com/hotel/test.html"
            "?checkin=2026-09-01&checkout=2026-09-05&group_adults=4"
            "&group_children=0&no_rooms=1"
        )

        result = SearchJourney(browser).run(make_booking())

        assert result.failure_code is FailureCode.STEP_FAILED
        assert result.failed_step.step is JourneyStep.VERIFY_CONTEXT

    def test_explicit_no_availability_fails_promptly(self):
        browser = _happy_browser()
        browser.page_text = "This property is not available for your dates"

        result = SearchJourney(browser).run(make_booking())

        assert result.failure_code is FailureCode.NO_EQUIVALENT_OFFER
        assert result.failed_step.step is JourneyStep.READ_ROOM_TABLE

    def test_non_booking_property_href_is_rejected(self):
        browser = _happy_browser()
        browser.property_url = "https://example.com/hotel/test.html"

        result = SearchJourney(browser).run(make_booking())

        assert not result.ok
        assert result.failed_step.step is JourneyStep.OPEN_PROPERTY


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
