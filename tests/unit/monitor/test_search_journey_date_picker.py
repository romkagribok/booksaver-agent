from __future__ import annotations

from dataclasses import replace
from datetime import date

import pytest

from booksaver.domain.journey import JourneyStep
from booksaver.domain.value_objects import Property, StayDates
from booksaver.monitor.search_journey import (
    SearchJourney,
    _calendar_nav_direction,
    _date_label_present,
    _months_from_data_dates,
    _parse_calendar_months,
    _property_already_in_form,
)

from .fakes import FakeInteractiveBrowser, make_booking


class TestCalendarHelpers:
    def test_parse_calendar_months_from_page_text(self):
        text = "Search hotels\nOctober 2026\nNovember 2026\nCalendar"
        months = _parse_calendar_months(text)
        assert months == [2026 * 12 + 9, 2026 * 12 + 10]

    def test_months_from_data_dates(self):
        months = _months_from_data_dates(
            ["2026-10-01", "2026-10-15", "2026-11-01", "bad"]
        )
        assert months == [2026 * 12 + 9, 2026 * 12 + 10]

    def test_nav_direction_goes_back_for_earlier_month(self):
        visible = _parse_calendar_months("October 2026\nNovember 2026")
        assert _calendar_nav_direction(date(2026, 8, 1), visible) == "prev"

    def test_nav_direction_goes_forward_for_later_month(self):
        visible = _parse_calendar_months("October 2026\nNovember 2026")
        assert _calendar_nav_direction(date(2026, 12, 1), visible) == "next"

    def test_nav_direction_raises_when_month_visible_but_day_missing(self):
        visible = _months_from_data_dates(["2026-08-02", "2026-09-01"])
        with pytest.raises(RuntimeError, match="day cell is missing"):
            _calendar_nav_direction(date(2026, 8, 1), visible)

    def test_date_label_present_matches_booking_style(self):
        assert _date_label_present("Mon, Aug 1 — Fri, Aug 5", date(2026, 8, 1))
        assert _date_label_present("September 1", date(2026, 9, 1))

    def test_property_already_in_form_detects_result_found(self):
        booking = make_booking()
        text = "The Westin Hapuna Beach Resort\n1 result found\nMon, Oct 5"
        assert _property_already_in_form(text, [], booking) is False
        westin = replace(
            make_booking(),
            property=Property(
                name="The Westin Hapuna Beach Resort",
                booking_com_ref=make_booking().property.booking_com_ref,
            ),
        )
        assert _property_already_in_form(text, [], westin)


class TestFillSearchGoal:
    def test_goal_focuses_on_dates_when_property_already_set(self):
        westin = replace(
            make_booking(),
            property=Property(
                name="The Westin Hapuna Beach Resort",
                booking_com_ref=make_booking().property.booking_com_ref,
            ),
            stay_dates=StayDates(check_in=date(2026, 8, 1), check_out=date(2026, 8, 5)),
        )
        browser = FakeInteractiveBrowser(
            page_text="The Westin Hapuna Beach Resort\n1 result found\nMon, Oct 5",
            search_box_value="The Westin Hapuna Beach Resort",
        )
        goal = SearchJourney(browser)._fill_search_goal(westin)
        assert "ALREADY set" in goal
        assert "do not" in goal.lower()
        assert "2026-08-01" in goal

    def test_scripted_fill_skips_search_box_when_property_set(self):
        westin = replace(
            make_booking(),
            property=Property(
                name="The Westin Hapuna Beach Resort",
                booking_com_ref=make_booking().property.booking_com_ref,
            ),
            stay_dates=StayDates(check_in=date(2026, 8, 1), check_out=date(2026, 8, 5)),
        )
        browser = FakeInteractiveBrowser(
            titles=["The Westin Hapuna Beach Resort"],
            page_text=(
                "The Westin Hapuna Beach Resort\n1 result found\n"
                "October 2026\nNovember 2026"
            ),
            calendar_month=date(2026, 10, 1),
            search_box_value="The Westin Hapuna Beach Resort",
        )
        browser.property_url = (
            "https://www.booking.com/hotel/test.html"
            "?checkin=2026-08-01&checkout=2026-08-05&group_adults=2"
        )
        result = SearchJourney(browser).run(westin)
        assert result.ok
        fills = [a for k, a in browser.actions if k == "fill" and 'name="ss"' in a]
        assert not fills


class TestCalendarNavigation:
    def test_pages_back_before_clicking_target_date(self):
        browser = FakeInteractiveBrowser(
            titles=["Hotel Test"],
            page_text="October 2026\nNovember 2026",
            calendar_month=date(2026, 10, 1),
        )
        browser.property_url = (
            "https://www.booking.com/hotel/test.html"
            "?checkin=2026-08-01&checkout=2026-08-05&group_adults=2"
        )
        booking = replace(
            make_booking(),
            stay_dates=StayDates(check_in=date(2026, 8, 1), check_out=date(2026, 8, 5)),
        )

        result = SearchJourney(browser).run(booking)
        assert result.ok

        prev_clicks = [
            action
            for kind, action in browser.actions
            if kind == "click" and "Previous month" in action
        ]
        assert prev_clicks
        date_clicks = [
            action
            for kind, action in browser.actions
            if kind == "click" and 'data-date="2026-08-01"' in action
        ]
        assert date_clicks
        assert any('data-date="2026-08-05"' in action for kind, action in browser.actions)

    def test_missing_date_cells_fail_fill_search(self):
        browser = FakeInteractiveBrowser(
            titles=["Hotel Test"],
            calendar_month=date(2026, 10, 1),
            fail_selectors={"data-date"},
        )
        browser.property_url = (
            "https://www.booking.com/hotel/test.html"
            "?checkin=2026-09-01&checkout=2026-09-05&group_adults=2"
        )
        result = SearchJourney(browser).run(make_booking())
        assert not result.ok
        assert result.failed_step.step is JourneyStep.FILL_SEARCH
