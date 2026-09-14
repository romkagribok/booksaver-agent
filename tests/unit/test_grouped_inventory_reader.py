from __future__ import annotations

import asyncio
from dataclasses import replace
from datetime import UTC, datetime

import pytest

import booksaver.infrastructure.browser.grouped_inventory_reader as reader
from booksaver.infrastructure.browser.inventory_link_resolution import ResolvedInventoryLink

ROOT = "https://secure.booking.com/mytrips.html"
TRIPS = [ROOT + "?trip_id=" + str(i) for i in range(2)]
DETAILS = [f"https://secure.booking.com/confirmation.en-us.html?auth_key={i}" for i in range(6)]


def snapshot(url, links=(), text="Confirmation number:123456\n" + "Confirmed page " * 10):
    return reader.InventorySnapshot(url, text, tuple(reader.RenderedLink(*x) for x in links), ())


class Browser:
    def __init__(self):
        self.url = ROOT
        self.history = []
        self.actions = 0
        self.pages = {ROOT: snapshot(ROOT, [(x, "Trip") for x in TRIPS])}
        for i, trip in enumerate(TRIPS):
            self.pages[trip] = snapshot(
                trip, [(x, "Hotel\nConfirmed") for x in DETAILS[i * 3 : i * 3 + 3]]
            )
        for detail in DETAILS:
            desktop = detail + "&prefer_site_type=www"
            self.pages[detail] = snapshot(detail, [(desktop, "Desktop version")])
            self.pages[desktop] = replace(snapshot(
                desktop,
                text="Booking Details\nYour room details\nPrice\nConfirmation number:123456\n"
                + "Confirmed page " * 10,
            ), hotel_anchors=(("Hotel", "https://www.booking.com/hotel/lt/test.html"),))

    async def get_current_page_url(self):
        return self.url

    async def navigate(self, link):
        assert link.source_url == self.url
        self.history.append(self.url)
        self.url = link.target_url
        self.actions += 1

    async def back(self, target):
        while self.history:
            self.url = self.history.pop()
            if self.url == target:
                break
        self.actions += 1
        return True


async def no_wait(*args):
    pass


def header_facts():
    return {"confirmation_id": "x", "property_name": "Hotel", "property_reference": "hotel",
            "check_in": "2026-10-23", "check_out": "2026-10-24"}


def harness(monkeypatch, browser, *, check=no_wait):
    async def read(session):
        return session.pages[session.url]

    async def resolve(session, *, source_url, observed_target_url):
        assert source_url == session.url
        if observed_target_url not in [x.url for x in session.pages[source_url].links]:
            return None
        return ResolvedInventoryLink(source_url, observed_target_url, "target", ())

    monkeypatch.setattr(reader, "read_inventory_snapshot", read)
    monkeypatch.setattr(reader, "resolve_rendered_inventory_link", resolve)
    monkeypatch.setattr(reader, "resolve_rendered_confirmation_view", resolve)
    monkeypatch.setattr(reader.asyncio, "sleep", no_wait)
    monkeypatch.setattr(
        reader, "parse_confirmation_facts", lambda *a, **k: header_facts()
    )
    result = reader.GroupedInventoryRead()
    worker = reader.GroupedInventoryReader(
        browser,
        navigate=browser.navigate,
        back=browser.back,
        check=check,
        observed_at=datetime.now(UTC),
        result=result,
    )
    return worker, result


def test_all_six_details_across_two_groups_continue_after_first_positive(monkeypatch):
    browser = Browser()
    worker, result = harness(monkeypatch, browser)
    assert asyncio.run(worker.run())
    assert len(result.reservations) == 6
    assert result.trip_groups == result.trips_visited == 2
    assert result.details_observed == 6
    assert result.unresolved == 0
    assert result.desktop_view_used
    assert browser.url == ROOT
    assert browser.actions == 22
    assert "auth_key" not in repr(result)


def test_duplicate_manage_links_do_not_repeat_details(monkeypatch):
    browser = Browser()
    page = browser.pages[TRIPS[0]]
    alias = DETAILS[0].replace("confirmation.en-us", "confirmation")
    browser.pages[TRIPS[0]] = snapshot(
        TRIPS[0], [(x.url, x.text) for x in page.links] + [(alias, "Manage")]
    )
    worker, result = harness(monkeypatch, browser)
    assert asyncio.run(worker.run())
    assert result.details_observed == 6


def test_explicit_inactive_skipped_unknown_status_still_inspected(monkeypatch):
    browser = Browser()
    browser.pages[TRIPS[0]] = snapshot(
        TRIPS[0],
        [(DETAILS[0], "Hotel\nCompleted"), (DETAILS[1], "Hotel\nCancelled"), (DETAILS[2], "Hotel")],
    )
    worker, result = harness(monkeypatch, browser)
    assert asyncio.run(worker.run())
    assert result.inactive_skipped == 2
    assert result.details_observed == 4


def test_unparseable_detail_stays_unresolved_and_other_groups_continue(monkeypatch):
    browser = Browser()
    worker, result = harness(monkeypatch, browser)
    def parse(*a, **kw):
        return None if browser.url.startswith(DETAILS[0]) else header_facts()

    monkeypatch.setattr(reader, "parse_confirmation_facts", parse)
    assert asyncio.run(worker.run())
    assert result.unresolved == 1
    assert result.trips_visited == 2
    assert len(result.reservations) == 5


def test_guard_stop_propagates_even_after_a_positive(monkeypatch):
    browser = Browser()

    async def check():
        if browser.actions > 7:
            raise PermissionError("guard")

    worker, result = harness(monkeypatch, browser, check=check)
    with pytest.raises(PermissionError):
        asyncio.run(worker.run())
    assert result.reservations
    assert result.trips_visited == 1


def test_no_grouped_layout_leaves_existing_agent_path_untouched(monkeypatch):
    browser = Browser()
    browser.pages[ROOT] = snapshot(ROOT, [(DETAILS[0], "Hotel")])
    worker, result = harness(monkeypatch, browser)
    assert not asyncio.run(worker.run())
    assert browser.actions == 0
    assert not result.desktop_view_used


def test_lost_link_stops_with_unresolved_coverage(monkeypatch):
    browser = Browser()
    worker, result = harness(monkeypatch, browser)

    async def missing(*a, **kw):
        return None

    monkeypatch.setattr(reader, "resolve_rendered_inventory_link", missing)
    assert asyncio.run(worker.run())
    assert result.unresolved == 1
    assert not result.reservations
    assert browser.actions == 0


def test_bad_history_is_bounded_and_never_claims_success(monkeypatch):
    browser = Browser()
    worker, result = harness(monkeypatch, browser)

    async def stuck(target):
        browser.actions += 1
        return True

    worker.back = stuck
    assert asyncio.run(worker.run())
    assert result.unresolved == 1
    assert result.details_observed == 1
    assert browser.actions == 7


def test_desktop_session_taint_sticks_even_when_navigation_raises(monkeypatch):
    browser = Browser()
    worker, result = harness(monkeypatch, browser)
    original = worker.navigate

    async def navigate(link):
        if "prefer_site_type" in link.target_url:
            raise TimeoutError
        await original(link)

    worker.navigate = navigate
    with pytest.raises(TimeoutError):
        asyncio.run(worker.run())
    assert result.desktop_view_used


def test_trip_count_waits_for_cards_after_parent_shell_load(monkeypatch):
    browser = Browser()
    browser.pages[ROOT] = snapshot(ROOT, [(x, "Trip\n3 bookings") for x in TRIPS])
    worker, result = harness(monkeypatch, browser)
    reads = 0

    async def delayed(session):
        nonlocal reads
        if session.url == TRIPS[0]:
            reads += 1
            if reads < 4:
                return snapshot(TRIPS[0], text="Loading trip page " * 10)
        return session.pages[session.url]

    monkeypatch.setattr(reader, "read_inventory_snapshot", delayed)
    assert asyncio.run(worker.run())
    assert result.details_observed == 6
    assert result.unresolved == 0


def test_resolution_retries_fresh_links_without_extra_physical_actions(monkeypatch):
    browser = Browser()
    worker, result = harness(monkeypatch, browser)
    original = reader.resolve_rendered_inventory_link
    attempts = 0

    async def delayed(*a, **kw):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            return None
        return await original(*a, **kw)

    monkeypatch.setattr(reader, "resolve_rendered_inventory_link", delayed)
    assert asyncio.run(worker.run())
    assert result.details_observed == 6
    assert result.unresolved == 0
    assert browser.actions == 22


def test_mobile_confirmation_waits_for_full_details_link_before_parsing(monkeypatch):
    browser = Browser()
    worker, result = harness(monkeypatch, browser)
    reads = 0

    async def delayed(session):
        nonlocal reads
        if session.url == DETAILS[0]:
            reads += 1
            if reads < 4:
                return snapshot(DETAILS[0], text="Confirmation number:123456\n" + "Loading " * 30)
        return session.pages[session.url]

    def parse(text, *args, **kwargs):
        assert "Booking Details" in text and "Your room details" in text
        return header_facts()

    monkeypatch.setattr(reader, "read_inventory_snapshot", delayed)
    monkeypatch.setattr(reader, "parse_confirmation_facts", parse)
    assert asyncio.run(worker.run())
    assert result.details_observed == len(result.reservations) == 6
    assert result.unresolved == 0
    assert browser.actions == 22


def test_header_only_desktop_page_is_not_ready_for_fact_extraction():
    url = DETAILS[0] + "&prefer_site_type=www"
    partial = snapshot(url, text="Confirmation number:123456\nBooking Details\n" + "Loading " * 30)
    assert not reader.GroupedInventoryReader.ready(partial, desktop=True)


@pytest.mark.parametrize("label,skipped,unresolved", [("Car rental", 1, 0), ("Unknown item", 0, 1)])
def test_mixed_trip_skips_only_explicit_nonhotel_type(monkeypatch, label, skipped, unresolved):
    browser = Browser()
    browser.pages[ROOT] = snapshot(
        ROOT, [(TRIPS[0], "Trip\n4 bookings"), (TRIPS[1], "Trip\n3 bookings")]
    )
    group = browser.pages[TRIPS[0]]
    browser.pages[TRIPS[0]] = snapshot(
        TRIPS[0],
        [(x.url, x.text) for x in group.links]
        + [("https://cars.booking.com/manage-booking?id=private", label + "\nConfirmed")],
    )
    worker, result = harness(monkeypatch, browser)
    assert asyncio.run(worker.run())
    assert len(result.reservations) == 6
    assert result.nonhotel_skipped == skipped
    assert result.unresolved == unresolved
    assert browser.actions == 22


def test_desktop_section_skeleton_waits_for_property_and_settled_values(monkeypatch):
    browser = Browser()
    worker, result = harness(monkeypatch, browser)
    desktop = DETAILS[0] + "&prefer_site_type=www"
    loaded = browser.pages[desktop]
    reads = 0

    async def delayed(session):
        nonlocal reads
        if session.url == desktop:
            reads += 1
            if reads < 3:
                return replace(loaded, hotel_anchors=(), text=loaded.text + "Loading...")
            if reads == 3:
                return replace(loaded, text=loaded.text + "Loading price...")
        return session.pages[session.url]

    def parse(text, *args, **kwargs):
        if "Loading" in text:
            return {"confirmation_id": "x"}
        return header_facts()

    monkeypatch.setattr(reader, "read_inventory_snapshot", delayed)
    monkeypatch.setattr(reader, "parse_confirmation_facts", parse)
    assert asyncio.run(worker.run())
    assert reads == 5
    assert result.details_observed == len(result.reservations) == 6
    assert result.unresolved == 0
    assert browser.actions == 22


def test_trip_auxiliary_confirmation_link_is_not_a_seventh_reservation(monkeypatch):
    browser = Browser()
    browser.pages[ROOT] = snapshot(
        ROOT, [(TRIPS[0], "Trip\n3 bookings"), (TRIPS[1], "Trip\n3 bookings")]
    )
    group = browser.pages[TRIPS[0]]
    browser.pages[TRIPS[0]] = snapshot(
        TRIPS[0], [(x.url, x.text) for x in group.links]
        + [("https://secure.booking.com/confirmation.html?auth_key=other-token", "Manage booking")],
    )
    worker, result = harness(monkeypatch, browser)
    assert asyncio.run(worker.run())
    assert result.details_observed == len(result.reservations) == 6
    assert result.unresolved == 0
    assert result.auxiliary_links_skipped == 1
    assert browser.actions == 22


def test_unknown_card_status_still_requires_detail_inspection(monkeypatch):
    browser = Browser()
    browser.pages[ROOT] = snapshot(ROOT, [(TRIPS[0], "Trip\n1 booking")])
    browser.pages[TRIPS[0]] = snapshot(TRIPS[0], [(DETAILS[0], "Unknown accommodation")])
    worker, result = harness(monkeypatch, browser)
    assert asyncio.run(worker.run())
    assert result.details_observed == len(result.reservations) == 1
    assert result.unresolved == 0


def test_confirmed_car_booking_route_accounts_for_trip_without_navigation(monkeypatch):
    browser = Browser()
    root = browser.pages[ROOT]
    browser.pages[ROOT] = replace(root, links=(
        reader.RenderedLink(TRIPS[0], "Trip", booking_count=4),
        reader.RenderedLink(TRIPS[1], "Trip", booking_count=3),
    ))
    group = browser.pages[TRIPS[0]]
    car = reader.RenderedLink(
        "https://cars.booking.com/my-booking/123456789?preflang=en", "Confirmed",
    )
    # Repeated rendered links do not inflate the distinct non-hotel count.
    browser.pages[TRIPS[0]] = replace(group, links=group.links + (car, car))
    worker, result = harness(monkeypatch, browser)
    destinations = []
    original = browser.navigate

    async def navigate(link):
        destinations.append(link.target_url)
        await original(link)

    worker.navigate = navigate
    assert asyncio.run(worker.run())
    assert len(result.reservations) == result.details_observed == 6
    assert result.nonhotel_skipped == 1
    assert result.unresolved == 0
    assert browser.actions == 22
    assert all("cars.booking.com" not in url for url in destinations)
    assert reader.GroupedInventoryReader.targets(browser.pages[TRIPS[0]], "reservation_detail") == (
        list(group.links)
    )


@pytest.mark.parametrize("url,status", [
    ("https://cars.booking.com/my-booking/123456789", "Confirmed"),
    ("https://cars.booking.com/my-booking/123456789?preflang=en", "Confirmed"),
])
def test_confirmed_numeric_car_booking_route_is_counted_without_product_label(url, status):
    page = snapshot(TRIPS[0], [(url, status)])
    assert reader.GroupedInventoryReader.nonhotels(page) == 1


@pytest.mark.parametrize("url,status", [
    ("https://cars.booking.com.evil.example/my-booking/123456789", "Confirmed"),
    ("https://example.com/my-booking/123456789", "Confirmed"),
    ("https://secure.booking.com/my-booking/123456789", "Confirmed"),
    ("https://cars.booking.com/manage-booking/123456789", "Confirmed"),
    ("https://cars.booking.com/my-booking/not-a-number", "Confirmed"),
    ("https://cars.booking.com/my-booking/123456789/cancel", "Confirmed"),
    ("https://cars.booking.com/my-booking/123456789", "Cancelled"),
    ("https://cars.booking.com/my-booking/123456789", "Pending"),
    ("https://cars.booking.com/my-booking/123456789", "Unconfirmed"),
    ("https://user:password@cars.booking.com/my-booking/123456789", "Confirmed"),
    ("http://cars.booking.com/my-booking/123456789", "Confirmed"),
    ("https://cars.booking.com:443/my-booking/123456789", "Confirmed"),
    ("https://cars.booking.com:invalid/my-booking/123456789", "Confirmed"),
    ("https://cars.booking.com/my-booking/123456789#confirmation", "Confirmed"),
    ("https://cars.booking.com/my-booking/123456789?action=cancel", "Confirmed"),
    ("https://cars.booking.com/my-booking/123456789?preflang=en&preflang=fr", "Confirmed"),
])
def test_unqualified_car_route_or_status_does_not_count_as_nonhotel(url, status):
    assert reader.GroupedInventoryReader.nonhotels(snapshot(TRIPS[0], [(url, status)])) == 0


def test_unrelated_body_updates_do_not_reset_stable_booking_facts(monkeypatch):
    browser = Browser()
    worker, result = harness(monkeypatch, browser)
    desktop = DETAILS[0] + "&prefer_site_type=www"
    reads = 0

    async def changing_footer(session):
        nonlocal reads
        current = session.pages[session.url]
        if session.url == desktop:
            reads += 1
            return replace(current, text=current.text + f"\nPromotion update {reads}")
        return current

    monkeypatch.setattr(reader, "read_inventory_snapshot", changing_footer)
    assert asyncio.run(worker.run())
    assert reads == 2
    assert result.unresolved == 0
    assert len(result.reservations) == 6


def test_separately_rendered_count_handles_concatenated_date_and_count_text(monkeypatch):
    browser = Browser()
    root = browser.pages[ROOT]
    browser.pages[ROOT] = replace(root, links=tuple(
        reader.RenderedLink(trip, "Trip\nSep 13 – Sep 193 bookings", booking_count=3)
        for trip in TRIPS
    ))
    group = browser.pages[TRIPS[0]]
    browser.pages[TRIPS[0]] = replace(group, links=group.links + (
        reader.RenderedLink("https://secure.booking.com/confirmation.html?auth_key=alias",
                            "Manage booking"),))
    worker, result = harness(monkeypatch, browser)
    assert asyncio.run(worker.run())
    assert result.details_observed == 6
    assert result.auxiliary_links_skipped == 1
    assert result.unresolved == 0


def test_partial_step_diagnostic_contains_no_booking_or_url(monkeypatch, caplog):
    browser = Browser()
    worker, result = harness(monkeypatch, browser)

    async def missing(*args, **kwargs):
        return None

    monkeypatch.setattr(reader, "resolve_rendered_inventory_link", missing)
    assert asyncio.run(worker.run())
    assert result.unresolved == 1
    assert "step=trip_navigation count=1" in caplog.text
    assert "booking.com" not in caplog.text
    assert "auth_key" not in caplog.text
