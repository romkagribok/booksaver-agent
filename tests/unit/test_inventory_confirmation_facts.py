from datetime import UTC, datetime

import pytest

from booksaver.infrastructure.browser.inventory_confirmation_facts import parse_confirmation_facts

_NOW = datetime(2026, 9, 13, 20, tzinfo=UTC)
_ANCHORS = (("Synthetic Lake Hotel", "https://www.booking.com/hotel/lt/synthetic-lake.en-us.html"),)
_BODY = """Your stay is confirmed
Synthetic Lake Hotel
Check-in
Fri, Oct 23, 2026
from 14:00
Check-out
Sat, Oct 24, 2026
until 12:00
Change dates
Booking Details
2 adults - 1 night, 1 rooms
Address
Synthetic Street
Confirmation number
1234567890
Your room details
Standard Double Room
Change your room
Guest name
Synthetic Guest
Cancellation cost

Free cancellation within: 1 month 9 days
until October 23, 2026 12:00 PM: € 0
from October 23, 2026 12:00 PM: € 100 – Changing the dates of your stay isn't possible.
Cancellation deadlines are in the property's local time.
1 room\t€ 89.29
12 % VAT\t€ 10.71
€ 2 City tax per person per night\t€ 4
Price
(for 2 guests)
€ 104
The final price shown is the amount you'll pay to the property.
Additional Info
Note that additional supplements (e.g. an extra bed) aren't added in this total.
"""


def _parse(body: str = _BODY, *, anchors=_ANCHORS, now: datetime = _NOW):
    return parse_confirmation_facts(body, anchors, observed_at=now)


def test_complete_explicit_single_room_confirmation_facts():
    facts = _parse()
    assert facts is not None
    assert facts["confirmation_id"] == facts["remote_id"] == "1234567890"
    assert facts["identity_evidence"] == "complete"
    assert facts["completeness"] == "incomplete"
    assert facts["scope"] == facts["lifecycle"] == "upcoming"
    assert facts["property_name"] == "Synthetic Lake Hotel"
    assert facts["property_reference"] == _ANCHORS[0][1]
    assert facts["check_in"] == "2026-10-23"
    assert facts["check_out"] == "2026-10-24"
    assert (facts["adults"], facts["children"], facts["rooms"]) == ("2", "0", "1")
    # Room, price and cancellation facts belong to the Jev path; this parser leaves them unknown.
    assert all(
        facts[key] == "unknown"
        for key in (
            "room_type", "booked_total", "currency", "all_in", "refundability", "refund_deadline",
        )
    )
    assert _reasons(_BODY) == {}
    assert all(isinstance(value, str) for value in facts.values())


@pytest.mark.parametrize("label", [
    "Confirmation number:1234567890", "Confirmation number: 1234567890",
])
def test_inline_confirmation_and_separate_pin_preserve_all_explicit_facts(label):
    body = _BODY.replace("Confirmation number\n1234567890", label + "\nPIN:9876")
    assert _parse(body) == _parse()


@pytest.mark.parametrize("inline", [False, True])
def test_footer_booking_details_navigation_preserves_header_guest_and_price_facts(inline):
    body = _BODY
    if inline:
        body = body.replace("Confirmation number\n1234567890", "Confirmation number:1234567890")
    assert _parse(body + "\nBooking Details\nCommunications") == _parse(body)


@pytest.mark.parametrize("extra", [
    "Booking Details\n2 adults - 1 night, 1 rooms\n",
    "Booking Details\n3 adults - 1 night, 1 rooms\n",
    "Booking Details\nCommunications\n",
])
def test_duplicate_guest_labels_inside_confirmation_header_remain_ambiguous(extra):
    body = _BODY.replace("Address\n", extra + "Address\n")
    facts = _parse(body + "\nBooking Details\nCommunications")
    assert facts is not None
    assert all(facts[field] == "unknown" for field in (
        "adults", "children", "rooms", "room_type", "booked_total", "all_in",
    ))


def test_guest_composition_after_confirmation_identity_is_not_header_evidence():
    body = _BODY.replace("Booking Details\n2 adults - 1 night, 1 rooms\n", "")
    facts = _parse(body + "\nBooking Details\n2 adults - 1 night, 1 rooms")
    assert facts is not None
    assert facts["adults"] == facts["room_type"] == facts["all_in"] == "unknown"


@pytest.mark.parametrize("boundary", ["Reference", "", "Confirmation number extra"])
def test_missing_confirmation_boundary_cannot_qualify_guest_summary(boundary):
    body = _BODY.replace("Confirmation number", boundary)
    assert _parse(body + "\nBooking Details\nCommunications") is None


@pytest.mark.parametrize("suffix", [
    "Confirmation number:1234567890", "Confirmation number:9999999999",
    "Confirmation number:unknown", "Confirmation number\n1234567890",
])
@pytest.mark.parametrize("inline", [False, True])
def test_duplicate_confirmation_labels_are_rejected_across_both_layouts(suffix, inline):
    body = _BODY
    if inline:
        body = body.replace("Confirmation number\n1234567890", "Confirmation number:1234567890")
    assert _parse(body + "\n" + suffix) is None


@pytest.mark.parametrize("inline", [
    "Confirmation number:1234", "Confirmation number:unknown",
    "Confirmation number:1234567890 PIN:9876", "Confirmation number:123456789012345678901",
    "Confirmation number:1234567890 extra text",
])
def test_inline_confirmation_keeps_existing_identity_bounds(inline):
    assert _parse(_BODY.replace("Confirmation number\n1234567890", inline)) is None


@pytest.mark.parametrize(
    "body",
    [
        _BODY.replace("Confirmation number", "Reference"),
        _BODY + "\nConfirmation number\n9999999999",
        _BODY.replace("1234567890", "unknown"),
        _BODY.replace("1234567890", "1234"),
        _BODY.replace("Your stay is confirmed", "Your stay might be confirmed"),
        _BODY + "\nYour stay is confirmed",
        _BODY + "\nYour booking has been cancelled.",
        _BODY + "\nYour reservation is canceled.",
        "x" * 250_001,
    ],
)
def test_unsupported_or_conflicting_identity_is_rejected(body):
    assert _parse(body) is None


def test_naive_observation_time_is_rejected():
    assert _parse(now=_NOW.replace(tzinfo=None)) is None


@pytest.mark.parametrize(
    "now, lifecycle, scope",
    [
        (datetime(2026, 10, 22, 20, tzinfo=UTC), "upcoming", "upcoming"),
        (datetime(2026, 10, 23, 20, tzinfo=UTC), "current", "upcoming"),
        (datetime(2026, 10, 24, 20, tzinfo=UTC), "completed", "past"),
    ],
)
def test_confirmed_dates_classify_lifecycle(now, lifecycle, scope):
    facts = _parse(now=now)
    assert facts is not None
    assert (facts["lifecycle"], facts["scope"]) == (lifecycle, scope)


@pytest.mark.parametrize(
    "change",
    [
        ("Fri, Oct 23, 2026", "Thu, Oct 23, 2026"),
        ("Sat, Oct 24, 2026", "Fri, Oct 23, 2026"),
        ("Fri, Oct 23, 2026", "23/10/2026"),
        ("Check-in", "Check-in\nFri, Oct 23, 2026\nCheck-in"),
    ],
)
def test_bad_or_ambiguous_stay_dates_do_not_infer_lifecycle_or_occupancy(change):
    facts = _parse(_BODY.replace(*change))
    assert facts is not None
    assert facts["lifecycle"] == facts["check_in"] == facts["check_out"] == "unknown"
    assert facts["adults"] == facts["rooms"] == facts["all_in"] == "unknown"


@pytest.mark.parametrize(
    "details",
    [
        "Max. 2 adults - 1 night, 1 rooms",
        "2 guests - 1 night, 1 rooms",
        "2 adults and 1 child - 1 night, 1 rooms",
        "2 adults - 1 night, 2 rooms",
        "2 adults - 2 nights, 1 rooms",
        "2 adults - 1 night, 1 rooms; additional guests allowed",
    ],
)
def test_only_closed_booked_single_unit_composition_qualifies(details):
    facts = _parse(_BODY.replace("2 adults - 1 night, 1 rooms", details))
    assert facts is not None
    assert facts["adults"] == facts["children"] == facts["rooms"] == "unknown"
    assert facts["room_type"] == facts["all_in"] == "unknown"


@pytest.mark.parametrize(
    "change",
    [
        ("Booking Details", "Booking Details\n2 adults - 1 night, 1 rooms\nBooking Details"),
        ("Your room details", "Your room details\nAnother Room\nYour room details"),
        ("Change your room", "Different Room"),
    ],
)
def test_duplicate_or_unsupported_room_sections_leave_room_unknown(change):
    facts = _parse(_BODY.replace(*change))
    assert facts is not None
    assert facts["room_type"] == "unknown"


@pytest.mark.parametrize(
    "anchors",
    [
        (),
        _ANCHORS * 2,
        (("Other Hotel", _ANCHORS[0][1]),),
        (("Synthetic Lake Hotel", "https://www.booking.com/hotel/lt/lake.html?auth_key=private"),),
        (("Synthetic Lake Hotel", "https://www.booking.com/hotel/lt/lake.html#rooms"),),
        (("Synthetic Lake Hotel", "https://user:secret@www.booking.com/hotel/lt/lake.html"),),
        (("Synthetic Lake Hotel", "https://www.booking.com.evil.test/hotel/lt/lake.html"),),
        (("Synthetic Lake Hotel", "http://www.booking.com/hotel/lt/lake.html"),),
        (("Synthetic Lake Hotel", "https://www.booking.com:443/hotel/lt/lake.html"),),
    ],
)
def test_property_requires_unique_header_anchor_and_canonical_safe_url(anchors):
    facts = _parse(anchors=anchors)
    assert facts is not None
    assert facts["property_name"] == facts["property_reference"] == "unknown"


def test_property_anchor_must_appear_before_check_in():
    facts = _parse(_BODY.replace("Synthetic Lake Hotel\n", "") + "\nSynthetic Lake Hotel")
    assert facts is not None
    assert facts["property_reference"] == "unknown"


def test_single_apartment_week_has_explicit_guest_facts():
    body = (
        _BODY.replace("Sat, Oct 24, 2026", "Fri, Oct 30, 2026")
        .replace("2 adults - 1 night, 1 rooms", "2 adults - 1 week, 1 apartment")
        .replace(
            "Standard Double Room\nChange your room",
            "Entire apartment\nOne-Bedroom Apartment\nGuest name",
        )
    )
    facts = _parse(body)
    assert facts is not None
    assert (facts["adults"], facts["children"], facts["rooms"]) == ("2", "0", "1")


def test_five_night_apartment_guest_summary_survives_late_navigation_label():
    body = (
        _BODY.replace("Sat, Oct 24, 2026", "Wed, Oct 28, 2026")
        .replace("2 adults - 1 night, 1 rooms", "2 adults - 5 nights, 1 apartment")
        .replace("1 room\t€ 89.29", "1 apartment\t€ 89.29")
        .replace(
            "€ 2 City tax per person per night\t€ 4", "€ 2 City tax per person per night\t€ 20",
        )
        .replace("€ 104", "€ 120")
        + "\nBooking Details\nCommunications"
    )
    facts = _parse(body)
    assert facts is not None
    assert (facts["adults"], facts["children"], facts["rooms"]) == ("2", "0", "1")


@pytest.mark.parametrize('heading', [
    'Your booking is cancelled', 'Your reservation has been canceled.', 'Your stay is cancelled!',
])
def test_explicit_cancelled_confirmation_has_identity_without_financial_guesses(heading):
    from booksaver.infrastructure.browser.inventory_confirmation_facts import (
        parse_cancelled_confirmation,
    )
    result = parse_cancelled_confirmation(heading + '\nConfirmation number: 1234500001')
    assert result is not None
    assert result['confirmation_id'] == '1234500001'
    assert result['lifecycle'] == 'cancelled'
    assert result['booked_total'] == 'unknown'

@pytest.mark.parametrize('text', [
    'Free cancellation\nConfirmation number: 1234500001',
    'Your booking is cancelled\nYour stay is confirmed\nConfirmation number: 1234500001',
    'Your booking is cancelled\nConfirmation number: 1234500001\nConfirmation number: 1234500002',
    'If your booking is cancelled you may receive a refund\nConfirmation number: 1234500001',
    'Your booking is cancelled',
])
def test_cancellation_requires_unambiguous_positive_identity_and_status(text):
    from booksaver.infrastructure.browser.inventory_confirmation_facts import (
        parse_cancelled_confirmation,
    )
    assert parse_cancelled_confirmation(text) is None


@pytest.mark.parametrize('confirmed', [
    'your stay is confirmed', 'YOUR BOOKING IS CONFIRMED', 'Confirmed!', 'UPCOMING',
])
def test_cancellation_contradictions_are_case_insensitive(confirmed):
    from booksaver.infrastructure.browser.inventory_confirmation_facts import (
        parse_cancelled_confirmation,
    )
    assert parse_cancelled_confirmation(
        f'Your booking is cancelled\n{confirmed}\nConfirmation number: 1234500001'
    ) is None


# The room section of the owner's own reservation, as rendered on the layout synchronization reads.
_OWNER_ROOM_ROWS = (
    "Guest name\nSynthetic Guest Edit guest name\nMax capacity\n2 adults\n"
    "Meal Plan\nNo meal is included in this room rate.\n"
    "Smoking preference\nNon-smoking room\nFacilities\nPrivate bathroom, Desk, Dining table\n"
)


def _meal(body: str) -> tuple[str, str]:
    facts = _parse(body)
    assert facts is not None
    return facts["meal_plan"], facts["meal_plan_text"]


def _with_room_rows(rows: str) -> str:
    return _BODY.replace("Guest name\nSynthetic Guest\n", rows)


def test_explicit_no_meal_row_is_recorded_with_its_wording():
    assert _meal(_with_room_rows(_OWNER_ROOM_ROWS)) == (
        "none", "No meal is included in this room rate.",
    )


@pytest.mark.parametrize(
    "row, expected",
    [
        ("Meal Plan\nBreakfast is included in the room rate.\n", "breakfast"),
        ("Meal Plan\tBreakfast is included in the room rate.\n", "breakfast"),
        ("Meal Plan: Breakfast & dinner included\n", "half_board"),
        ("Meal Plan\nAll-inclusive\n", "all_inclusive"),
        ("Meal Plan\nBreakfast costs \u20ac 15 per person per night.\n", "none"),
        # Unrecognized wording is never rounded to a value.
        ("Meal Plan\nSomething Booking.com has not said before\n", "unknown"),
        ("Meal Plan\nBreakfast & lunch included\n", "unknown"),
        ("Meal Plan\n2 meals per day\n", "unknown"),
        ("Meals are not included\n", "none"),
        ("Meal Plan No meal is included in this room rate.\n", "none"),
    ],
)
def test_labelled_meal_plan_row_is_authoritative(row, expected):
    body = _with_room_rows("Guest name\nSynthetic Guest\n" + row + "Smoking preference\nAny\n")
    assert _meal(body)[0] == expected


def test_standalone_inclusion_line_counts_when_no_row_is_labelled():
    body = _with_room_rows("Guest name\nSynthetic Guest\nBreakfast included\n")
    assert _meal(body) == ("breakfast", "Breakfast included")
    upsell = _with_room_rows(
        "Guest name\nSynthetic Guest\nBreakfast included\nAdd dinner for \u20ac 20\n"
    )
    assert _meal(upsell) == ("breakfast", "Breakfast included")


@pytest.mark.parametrize(
    "facilities",
    [
        "Facilities\nPrivate bathroom, Breakfast, Desk\n",
        "Facilities\nComplimentary breakfast, Desk\n",
        "Facilities: Complimentary breakfast, Desk\n",
        "Room facilities\tBreakfast included in the minibar, Desk\n",
    ],
)
def test_facilities_list_naming_a_meal_is_not_the_booked_meal_plan(facilities):
    rows = "Guest name\nSynthetic Guest\n" + facilities
    assert _meal(_with_room_rows(rows)) == ("none", "unknown")
    stated = _with_room_rows(rows + "Breakfast included\n")
    assert _meal(stated) == ("breakfast", "Breakfast included")
    labelled = _with_room_rows(rows + "Meal Plan\nNo meal is included in this room rate.\n")
    assert _meal(labelled) == ("none", "No meal is included in this room rate.")


def test_unrecognized_free_text_in_the_section_is_not_kept():
    body = _with_room_rows("Guest name\nSynthetic Guest\nPlease serve breakfast early\n")
    assert _meal(body) == ("unknown", "unknown")
    labelled = _with_room_rows("Guest name\nSynthetic Guest\nMeal Plan\nBrunch plan\n")
    assert _meal(labelled) == ("unknown", "Brunch plan")
    inline = _with_room_rows("Guest name\nSynthetic Guest\nMeal Plan: All-inclusive\n")
    assert _meal(inline) == ("all_inclusive", "All-inclusive")


def test_page_that_states_nothing_means_no_meals_only_when_the_section_was_read():
    # Owner decision: silence means no meals. It carries no text, so a stated plan can replace it.
    assert _meal(_BODY) == ("none", "unknown")
    without_guest_row = _BODY.replace("Guest name\nSynthetic Guest\n", "")
    assert _meal(without_guest_row) == ("unknown", "unknown")
    without_room = _BODY.replace("Your room details", "Your accommodation")
    assert _meal(without_room) == ("unknown", "unknown")


def test_meal_wording_outside_the_room_section_is_ignored():
    body = _BODY.replace("Additional Info\n", "Additional Info\nBreakfast included\n")
    assert _meal(body) == ("none", "unknown")


def test_conflicting_labelled_rows_and_long_wording_stay_bounded():
    rows = "Guest name\nSynthetic Guest\nMeal Plan\nBreakfast included\nMeal Plan\nAll-inclusive\n"
    assert _meal(_with_room_rows(rows))[0] == "unknown"
    long_row = "Guest name\nSynthetic Guest\nMeal Plan\nBreakfast included " + "x" * 400 + "\n"
    plan, text = _meal(_with_room_rows(long_row))
    assert plan == "breakfast" and len(text) == 200


def _reasons(body: str) -> dict[str, str]:
    reasons: dict[str, str] = {}
    assert parse_confirmation_facts(body, _ANCHORS, observed_at=_NOW, reasons=reasons) is not None
    return reasons


def test_meals_are_read_whatever_lines_precede_the_room_name():
    body = _BODY.replace(
        "Standard Double Room\nChange your room",
        "Private suite\nDeluxe Queen Bed\nChange your room\nMeal Plan\n"
        "No meal is included in this room rate.",
    )
    facts = _parse(body)
    assert facts is not None
    assert facts["meal_plan"] == "none"
    assert facts["meal_plan_text"] == "No meal is included in this room rate."

