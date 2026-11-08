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


def _reasons(body: str) -> dict[str, str]:
    reasons: dict[str, str] = {}
    assert parse_confirmation_facts(body, _ANCHORS, observed_at=_NOW, reasons=reasons) is not None
    return reasons


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
    # Room, party, meals, price and refund facts belong to Jev; this parser leaves them unknown.
    assert all(
        facts[key] == "unknown"
        for key in (
            "room_type", "adults", "children", "rooms", "meal_plan", "booked_total", "currency",
            "all_in", "refundability", "refund_deadline",
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


@pytest.mark.parametrize("suffix", ["?auth_key=private&aid=1", "#rooms"])
def test_a_hotel_link_keeps_the_property_without_its_query(suffix):
    url = _ANCHORS[0][1]
    facts = _parse(anchors=(("Synthetic Lake Hotel", url + suffix),))
    assert facts is not None and facts["property_reference"] == url


def test_property_anchor_must_appear_before_check_in():
    facts = _parse(_BODY.replace("Synthetic Lake Hotel\n", "") + "\nSynthetic Lake Hotel")
    assert facts is not None
    assert facts["property_reference"] == "unknown"


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
