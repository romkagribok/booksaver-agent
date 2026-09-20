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
    assert result.inactive_skipped == 1
    assert result.details_observed == 5
    assert result.unresolved > 0


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
    # The unknown target remains inspected after the bounded readiness wait; its label cannot
    # corroborate the parent count or turn coverage into a completed claim.
    assert result.unresolved == 1


def test_aliases_do_not_end_wait_before_late_status_cards_render(monkeypatch):
    browser = Browser()
    browser.pages[ROOT] = snapshot(ROOT, [(TRIPS[0], "Trip\n3 bookings")])
    late = browser.pages[TRIPS[0]]
    early = snapshot(TRIPS[0], [
        (DETAILS[0], "First Hotel\nConfirmed"),
        (DETAILS[3], "Manage first booking"),
        (DETAILS[4], "Manage reservation"),
    ])
    browser.pages[TRIPS[0]] = early
    worker, result = harness(monkeypatch, browser)
    group_reads = 0
    destinations = []
    navigate = browser.navigate

    async def delayed(session):
        nonlocal group_reads
        if session.url == TRIPS[0]:
            group_reads += 1
            if group_reads >= 5:
                browser.pages[TRIPS[0]] = late
        return browser.pages[session.url]

    async def observe_navigation(link):
        destinations.append(link.target_url)
        await navigate(link)

    monkeypatch.setattr(reader, "read_inventory_snapshot", delayed)
    worker.navigate = observe_navigation
    assert asyncio.run(worker.run())
    assert group_reads >= 5
    assert result.details_observed == len(result.reservations) == 3
    assert result.unresolved == 0
    assert all(detail in destinations for detail in DETAILS[:3])
    assert all(alias not in destinations for alias in DETAILS[3:5])


@pytest.mark.parametrize("expected,status_count", [(3, 1), (2, 3)])
def test_persistent_status_count_mismatch_waits_then_inspects_unknown_targets(
    monkeypatch, caplog, expected, status_count,
):
    browser = Browser()
    browser.pages[ROOT] = snapshot(ROOT, [(TRIPS[0], f"Trip\n{expected} bookings")])
    browser.pages[TRIPS[0]] = snapshot(TRIPS[0], [
        (url, "Hotel\nConfirmed" if index < status_count else "Unknown accommodation")
        for index, url in enumerate(DETAILS[:3])
    ])
    worker, result = harness(monkeypatch, browser)
    sleeps = 0

    async def count_wait(*args):
        nonlocal sleeps
        sleeps += 1

    monkeypatch.setattr(reader.asyncio, "sleep", count_wait)
    assert asyncio.run(worker.run())
    assert sleeps >= 20
    assert result.details_observed == len(result.reservations) == 3
    assert result.unresolved == 1
    assert "step=trip_card_count count=1" in caplog.text
    assert result.auxiliary_links_skipped == 0
    assert result.verified_trip_counts == 0


def test_status_card_count_is_unique_and_not_hidden_by_longer_manage_alias():
    page = snapshot(TRIPS[0], [
        (DETAILS[0], "Hotel\nConfirmed"),
        (DETAILS[0], "A much longer management link without a status label"),
        (DETAILS[0].replace("confirmation.en-us", "confirmation"), "Hotel\nConfirmed"),
    ])
    cards = reader.GroupedInventoryReader.targets(page, "reservation_detail", status_only=True)
    assert len(cards) == 1
    assert cards[0].text == "Hotel\nConfirmed"
    assert reader.GroupedInventoryReader.reservation_targets(page, 1) == cards


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


def test_root_detail_count_is_unknown_until_a_qualified_root_is_read(monkeypatch):
    browser = Browser()
    browser.url = TRIPS[0]
    worker, result = harness(monkeypatch, browser)
    assert result.root_detail_count is None
    assert not asyncio.run(worker.run())
    assert result.root_detail_count is None
    assert result.verified_trip_counts == 0


def test_initial_root_direct_details_are_recorded_even_when_group_scan_succeeds(monkeypatch):
    browser = Browser()
    root = browser.pages[ROOT]
    browser.pages[ROOT] = replace(root, links=root.links + (
        reader.RenderedLink(DETAILS[0], "Direct booking\nConfirmed"),
        reader.RenderedLink(DETAILS[0], "Manage direct booking"),
    ))
    worker, result = harness(monkeypatch, browser)
    assert asyncio.run(worker.run())
    assert result.root_detail_count == 1
    assert result.verified_trip_counts == 0  # Neither parent supplied an explicit count.
    assert len(result.reservations) == 6


def test_inactive_only_groups_have_explicit_verified_counts_without_detail_navigation(monkeypatch):
    browser = Browser()
    browser.pages[ROOT] = snapshot(ROOT, [(url, "Trip\n3 bookings") for url in TRIPS])
    for trip in TRIPS:
        group = browser.pages[trip]
        browser.pages[trip] = replace(group, links=tuple(
            replace(link, text="Hotel\nCompleted") for link in group.links
        ))
    worker, result = harness(monkeypatch, browser)
    assert asyncio.run(worker.run())
    assert result.root_detail_count == 0
    assert result.verified_trip_counts == result.trip_groups == result.trips_visited == 2
    assert result.inactive_skipped == 6
    assert result.details_observed == result.unresolved == 0
    assert result.reservations == []
    assert browser.actions == 4
    assert result.diagnostic()["verified_trip_counts"] == 2
    assert result.diagnostic()["root_detail_count"] == 0


@pytest.mark.parametrize("expected,verified,unresolved", [(1, 1, 0), (2, 0, 2), (None, 0, 1)])
def test_car_only_group_requires_exact_explicit_count_to_avoid_unresolved_empty_trip(
    monkeypatch, expected, verified, unresolved,
):
    browser = Browser()
    browser.pages[ROOT] = replace(browser.pages[ROOT], links=(
        reader.RenderedLink(TRIPS[0], "Trip", booking_count=expected),
    ))
    browser.pages[TRIPS[0]] = snapshot(TRIPS[0], [
        ("https://cars.booking.com/my-booking/123456789?preflang=en", "Confirmed"),
    ])
    worker, result = harness(monkeypatch, browser)
    assert asyncio.run(worker.run())
    assert result.root_detail_count == 0
    assert result.verified_trip_counts == verified
    assert result.nonhotel_skipped == 1
    assert result.unresolved == unresolved
    assert result.reservations == []
    assert browser.actions == 2


@pytest.mark.parametrize("active", ["Confirmed", "Upcoming", "In progress"])
@pytest.mark.parametrize("inactive", ["Completed", "Cancelled"])
def test_conflicting_active_inactive_card_is_inspected_and_cannot_establish_empty(
    monkeypatch, caplog, active, inactive,
):
    browser = Browser()
    browser.pages[ROOT] = snapshot(ROOT, [(TRIPS[0], "Trip\n1 booking")])
    browser.pages[TRIPS[0]] = snapshot(TRIPS[0], [
        (DETAILS[0], f"Hotel\n{active}\n{inactive}"),
    ])
    worker, result = harness(monkeypatch, browser)
    assert asyncio.run(worker.run())
    assert result.inactive_skipped == 0
    assert result.details_observed == len(result.reservations) == 1
    assert result.verified_trip_counts == 1
    assert result.unresolved == 1
    assert "step=conflicting_card_status count=1" in caplog.text


@pytest.mark.parametrize("expected", [None, 1])
def test_unknown_empty_group_never_has_verified_count(monkeypatch, expected):
    browser = Browser()
    browser.pages[ROOT] = replace(browser.pages[ROOT], links=(
        reader.RenderedLink(TRIPS[0], "Trip", booking_count=expected),
    ))
    browser.pages[TRIPS[0]] = snapshot(TRIPS[0])
    worker, result = harness(monkeypatch, browser)
    assert asyncio.run(worker.run())
    assert result.verified_trip_counts == 0
    assert result.unresolved > 0
    assert result.reservations == []


def test_active_status_on_canonical_alias_prevents_inactive_only_empty_evidence(monkeypatch):
    browser = Browser()
    browser.pages[ROOT] = snapshot(ROOT, [(TRIPS[0], "Trip\n1 booking")])
    browser.pages[TRIPS[0]] = snapshot(TRIPS[0], [
        (DETAILS[0], "Longer hotel card label\nCompleted"),
        (DETAILS[0].replace("confirmation.en-us", "confirmation"), "Confirmed"),
    ])
    worker, result = harness(monkeypatch, browser)
    assert asyncio.run(worker.run())
    assert result.inactive_skipped == 0
    assert result.details_observed == len(result.reservations) == 1
    assert result.verified_trip_counts == 1
    assert result.unresolved == 1


def test_cancelled_card_is_opened_and_exact_confirmation_recorded(monkeypatch):
    browser = Browser()
    browser.pages[TRIPS[0]] = snapshot(TRIPS[0], [(DETAILS[0], 'Hotel\nCancelled')])
    browser.pages[DETAILS[0]] = replace(snapshot(DETAILS[0], text=(
        'Your booking is cancelled\nConfirmation number: 1234500001')), cancelled_header=True)
    worker, result = harness(monkeypatch, browser)
    assert asyncio.run(worker.run())
    assert result.cancelled_confirmation_ids == {'1234500001'}
    assert any(r['lifecycle'] == 'cancelled' for r in result.reservations)
    assert not result.active_coverage_complete


def qualified_browser(monkeypatch):
    browser = Browser()
    browser.pages[ROOT] = replace(
        snapshot(ROOT, [(x, 'Trip', 3) for x in TRIPS]),
        active_root_total=2, active_root_urls=tuple(TRIPS)
    )
    worker, result = harness(monkeypatch, browser)
    def parse(*args, **kwargs):
        identity = next(
            str(i + 100000) for i, url in enumerate(DETAILS) if browser.url.startswith(url)
        )
        return {**header_facts(), 'confirmation_id': identity, 'lifecycle': 'upcoming'}
    monkeypatch.setattr(reader, 'parse_confirmation_facts', parse)
    return browser, worker, result


def test_explicit_root_total_exact_groups_and_identities_qualify_coverage(monkeypatch):
    browser, worker, result = qualified_browser(monkeypatch)
    assert asyncio.run(worker.run())
    assert result.active_coverage_complete


def test_stable_root_without_positive_total_is_not_complete(monkeypatch):
    browser, worker, result = qualified_browser(monkeypatch)
    browser.pages[ROOT] = replace(browser.pages[ROOT], active_root_total=None)
    assert asyncio.run(worker.run())
    assert not result.active_coverage_complete


def test_unknown_lifecycle_prevents_absence_authority(monkeypatch):
    browser, worker, result = qualified_browser(monkeypatch)
    monkeypatch.setattr(reader, 'parse_confirmation_facts', lambda *a, **k: header_facts())
    assert asyncio.run(worker.run())
    assert not result.active_coverage_complete


def test_group_count_mismatch_prevents_absence_authority(monkeypatch):
    browser, worker, result = qualified_browser(monkeypatch)
    browser.pages[ROOT] = replace(
        snapshot(ROOT, [(x, 'Trip', 4) for x in TRIPS]),
        active_root_total=2, active_root_urls=tuple(TRIPS)
    )
    assert asyncio.run(worker.run())
    assert not result.active_coverage_complete


def test_root_count_cannot_substitute_a_trip_outside_the_active_list(monkeypatch):
    browser, worker, result = qualified_browser(monkeypatch)
    browser.pages[ROOT] = replace(browser.pages[ROOT], active_root_urls=(
        TRIPS[0], 'https://outside.example/mytrips.html?trip_id=9',
    ))
    assert asyncio.run(worker.run())
    assert not result.active_coverage_complete


def test_root_membership_changes_during_scan_block_retirement(monkeypatch):
    browser, worker, result = qualified_browser(monkeypatch)
    original_back = worker.back
    returns = 0
    async def changed_back(target):
        nonlocal returns
        outcome = await original_back(target)
        if target == ROOT:
            returns += 1
            if returns == 2:
                browser.pages[ROOT] = replace(browser.pages[ROOT], active_root_urls=(
                    TRIPS[0], ROOT + '?trip_id=new',
                ))
        return outcome
    worker.back = changed_back
    assert asyncio.run(worker.run())
    assert not result.active_coverage_complete


@pytest.mark.parametrize('recovered', [True, False])
def test_restored_root_reloads_once_and_requires_fresh_scope(monkeypatch, recovered):
    browser, worker, result = qualified_browser(monkeypatch)
    original = browser.pages[ROOT]
    original_back = worker.back
    calls = []

    async def torn_down_back(target):
        outcome = await original_back(target)
        if target == ROOT:
            browser.pages[ROOT] = replace(original, active_root_total=None, active_root_urls=())
        return outcome

    async def refresh(target):
        calls.append(target)
        if recovered:
            browser.pages[ROOT] = original
        return True

    worker.back = torn_down_back
    worker.refresh_root = refresh
    assert asyncio.run(worker.run())
    assert calls == [ROOT]
    assert result.active_coverage_complete is recovered


def test_root_scope_that_settles_does_not_need_navigation(monkeypatch):
    browser, worker, result = qualified_browser(monkeypatch)
    original = browser.pages[ROOT]
    reads = 0

    async def read(session):
        nonlocal reads
        reads += 1
        return replace(original, active_root_total=None) if reads < 3 else original

    async def forbidden_refresh(target):
        raise AssertionError('Settled proof needs no reload')

    monkeypatch.setattr(reader, 'read_inventory_snapshot', read)
    worker.refresh_root = forbidden_refresh
    assert asyncio.run(worker.final_root_snapshot(original)) == original
    assert reads == 3


@pytest.mark.parametrize('change', ['unproven_initial', 'membership', 'url', 'known_count'])
def test_refresh_does_not_erase_conflicting_or_missing_initial_evidence(monkeypatch, change):
    browser, worker, result = qualified_browser(monkeypatch)
    original = browser.pages[ROOT]
    current = replace(original, active_root_total=None)
    if change == 'unproven_initial':
        original = current
    elif change == 'membership':
        current = replace(current, links=current.links[:1])
    elif change == 'url':
        current = replace(current, url=TRIPS[0])
    else:
        current = replace(current, active_root_total=3)
    browser.pages[ROOT] = current

    async def forbidden_refresh(target):
        raise AssertionError('Changed evidence must remain incomplete')

    worker.refresh_root = forbidden_refresh
    assert asyncio.run(worker.final_root_snapshot(original)) == current


def test_root_refresh_failure_preserves_incomplete_evidence(monkeypatch):
    browser, worker, result = qualified_browser(monkeypatch)
    original = browser.pages[ROOT]
    current = replace(original, active_root_total=None)
    browser.pages[ROOT] = current
    calls = []

    async def refresh(target):
        calls.append(target)
        return False

    worker.refresh_root = refresh
    assert asyncio.run(worker.final_root_snapshot(original)) == current
    assert calls == [ROOT]


def test_fresh_root_tracking_parameters_do_not_change_trip_identity(monkeypatch):
    browser, worker, result = qualified_browser(monkeypatch)
    original_back = worker.back

    async def changed_tracking(target):
        outcome = await original_back(target)
        if target == ROOT:
            browser.pages[ROOT] = replace(browser.pages[ROOT], active_root_urls=tuple(
                url + '&aid=123&label=fresh' for url in reversed(TRIPS)))
        return outcome

    worker.back = changed_tracking
    assert asyncio.run(worker.run())
    assert result.active_coverage_complete


def test_final_proof_on_a_different_page_cannot_retire_reservations(monkeypatch):
    browser, worker, result = qualified_browser(monkeypatch)

    async def substituted_root(root):
        return replace(root, url=TRIPS[0])

    worker.final_root_snapshot = substituted_root
    assert asyncio.run(worker.run())
    assert not result.active_coverage_complete


def test_empty_final_proof_must_still_belong_to_root(monkeypatch):
    browser = Browser()
    worker, result = harness(monkeypatch, browser)
    empty = replace(snapshot(ROOT), active_root_total=0)
    values = iter([empty, replace(empty, url=TRIPS[0])])

    async def read(session):
        return next(values)

    monkeypatch.setattr(reader, 'read_inventory_snapshot', read)
    assert not asyncio.run(worker.run())
    assert not result.active_coverage_complete
