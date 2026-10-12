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
    assert facts["room_type"] == "Standard Double Room"
    assert (facts["adults"], facts["children"], facts["rooms"]) == ("2", "0", "1")
    assert (facts["booked_total"], facts["currency"], facts["all_in"]) == ("104", "EUR", "explicit")
    assert facts["refundability"] == "explicit_refundable"
    assert facts["refund_deadline"] == "2026-10-23"
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
    "now, lifecycle, scope, refundable",
    [
        (datetime(2026, 10, 22, 20, tzinfo=UTC), "upcoming", "upcoming", "explicit_refundable"),
        (datetime(2026, 10, 23, 20, tzinfo=UTC), "current", "upcoming", "unknown"),
        (datetime(2026, 10, 24, 20, tzinfo=UTC), "completed", "past", "explicit_nonrefundable"),
    ],
)
def test_confirmed_dates_classify_lifecycle_and_local_deadline_boundary(
    now, lifecycle, scope, refundable,
):
    facts = _parse(now=now)
    assert facts is not None
    assert (facts["lifecycle"], facts["scope"], facts["refundability"]) == (
        lifecycle, scope, refundable,
    )
    if refundable != "explicit_refundable":
        assert facts["refund_deadline"] == "unknown"


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


@pytest.mark.parametrize(
    "change",
    [
        ("€ 104", "€ 100"),  # city tax excluded from displayed headline
        ("€ 104", "€ 104.000"),
        ("€ 104", "€ NaN"),
        ("€ 104", "$ 104"),
        ("€ 10.71", "€ 10.72"),
        ("€ 2 City tax per person per night\t€ 4", "€ 2 City tax per person per night\t€ 3"),
        ("Price\n", "Price\n€ 104\nPrice\n"),
        ("(for 2 guests)", "(for 3 guests)"),
        ("12 % VAT\t€ 10.71", "Service charge\t€ 10.71"),
        ("The final price shown is the amount you'll pay to the property.", "Amount paid so far."),
    ],
)
def test_unqualified_or_conflicting_price_is_unknown(change):
    facts = _parse(_BODY.replace(*change))
    assert facts is not None
    assert facts["booked_total"] == facts["currency"] == facts["all_in"] == "unknown"


@pytest.mark.parametrize(
    "extra",
    [
        "City tax is not included in your total.",
        "An extra cleaning fee is collected separately.",
        "Additional charges\nCity tax € 4",
        "This price is approximate.",
        "A mandatory resort fee is paid at the property.",
    ],
)
def test_mandatory_extra_or_approximate_charge_prevents_all_in(extra):
    facts = _parse(_BODY + "\n" + extra)
    assert facts is not None
    assert facts["all_in"] == "unknown"


@pytest.mark.parametrize("extra", [
    "Mandatory cleaning fee €25",
    "Resort fee €10",
    "City tax €4",
    "€ 2 City tax per person per night € 4",
])
@pytest.mark.parametrize("placement", ["before_price", "after_statement"])
def test_simple_total_rejects_unreconciled_monetary_charge_outside_components(extra, placement):
    body = (
        _BODY.replace("1 room\t", extra + "\n1 room\t")
        if placement == "before_price"
        else _BODY + "\n" + extra
    )
    facts = _parse(body)
    assert facts is not None
    assert facts["booked_total"] == facts["currency"] == facts["all_in"] == "unknown"


@pytest.mark.parametrize("extra", [
    "Final Price\n€105",
    "Final Price\n€105\nFinal Price\n€106",
    "Final Price:\n€104\nFINAL PRICE\n€104",
])
def test_simple_price_rejects_any_extra_final_price_section_including_duplicates(extra):
    facts = _parse(_BODY + "\n" + extra)
    assert facts is not None
    assert facts["booked_total"] == facts["currency"] == facts["all_in"] == "unknown"


@pytest.mark.parametrize(
    "change",
    [
        ("until October 23, 2026 12:00 PM: € 0", "until October 23, 2026 12:00 PM: € 10"),
        ("from October 23, 2026 12:00 PM: € 100", "from October 23, 2026 12:00 PM: € 0"),
        ("from October 23, 2026 12:00 PM", "from October 24, 2026 12:00 PM"),
        ("until October 23, 2026 12:00 PM: € 0", "until October 23, 2026 12:00 PM: € NaN"),
        ("Cancellation cost", "Cancellation cost\nCancellation cost"),
        ("until October 23, 2026 12:00 PM: € 0", ""),
    ],
)
def test_relative_banner_without_unambiguous_free_then_paid_tiers_is_insufficient(change):
    facts = _parse(_BODY.replace(*change))
    assert facts is not None
    assert facts["refundability"] == facts["refund_deadline"] == "unknown"


def test_tomorrows_utc_date_does_not_prove_local_refund_deadline_is_future():
    facts = _parse(now=datetime(2026, 10, 22, 23, tzinfo=UTC))
    assert facts is not None
    # At UTC+14 the local noon deadline has already passed.
    assert facts["refundability"] == "unknown"


def test_yesterdays_utc_date_does_not_prove_local_refund_deadline_expired():
    facts = _parse(
        _BODY.replace("12:00 PM", "11:59 PM"), now=datetime(2026, 10, 24, 1, tzinfo=UTC)
    )
    assert facts is not None
    # At UTC-12 the previous local calendar day is still in progress before its cutoff.
    assert facts["refundability"] == "unknown"


def test_truncated_cancellation_section_cannot_hide_later_contradictory_tier():
    body = _BODY.replace(
        "1 room\t€ 89.29", "\n".join(["Unrecognized policy detail"] * 16) + "\n1 room\t€ 89.29"
    )
    facts = _parse(body)
    assert facts is not None
    assert facts["refundability"] == "unknown"


def test_single_apartment_week_has_explicit_facts_but_approximate_extras_do_not_become_all_in():
    body = (
        _BODY.replace("Sat, Oct 24, 2026", "Fri, Oct 30, 2026")
        .replace("2 adults - 1 night, 1 rooms", "2 adults - 1 week, 1 apartment")
        .replace(
            "Standard Double Room\nChange your room",
            "Entire apartment\nOne-Bedroom Apartment\nGuest name",
        )
        .replace("1 room\t€ 89.29", "1 apartment\t€ 556.36")
        .replace("12 % VAT\t€ 10.71", "10 % VAT\t€ 55.64")
        .replace("€ 2 City tax per person per night\t€ 4\n", "")
        .replace("€ 104", "€ 612")
        + "\nAdditional charges\nThe price below is approximate and may include maximum occupancy."
        "\nCity tax (€ 3.00 × 2 guests × 7 nights) € 24\nFinal Price (taxes included)\n€ 636"
    )
    facts = _parse(body)
    assert facts is not None
    assert facts["room_type"] == "One-Bedroom Apartment"
    assert (facts["adults"], facts["children"], facts["rooms"]) == ("2", "0", "1")
    assert facts["refundability"] == "explicit_refundable"
    assert facts["booked_total"] == facts["all_in"] == "unknown"


_ADDITIONAL_PRICE = """1 room € 86.79
12 % VAT € 10.41
Price
(for 2 guests)
€ 97.20
Additional charges
The price you see below is an approximate that may include fees based on the maximum occupancy. This can include taxes set by local governments or charges set by the property.
City tax (€2.00 × 2 guests × 1 night) €4
Final Price
(taxes included)
€101.20
The final price shown is the amount you'll pay to the property.
"""  # noqa: E501
_ADDITIONAL_BODY = _BODY[:_BODY.index("1 room\t")] + _ADDITIONAL_PRICE


def test_additional_city_tax_is_all_in_only_after_exact_booked_party_calculation():
    facts = _parse(_ADDITIONAL_BODY)
    assert facts is not None
    assert (facts["adults"], facts["children"], facts["rooms"]) == ("2", "0", "1")
    assert (facts["booked_total"], facts["currency"], facts["all_in"]) == (
        "101.20", "EUR", "explicit",
    )
    assert facts["refundability"] == "explicit_refundable"


def test_late_navigation_label_preserves_additional_tax_layout_facts():
    body = _ADDITIONAL_BODY + "\nBooking Details\nCommunications"
    assert _parse(body) == _parse(_ADDITIONAL_BODY)


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
    assert facts["room_type"] == "Standard Double Room"
    assert (facts["booked_total"], facts["all_in"]) == ("120", "explicit")


@pytest.mark.parametrize("change", [
    ("× 2 guests", "× 3 guests"),
    ("× 1 night", "× 2 nights"),
    ("€2.00", "€3.00"),
    (
        "City tax (€2.00 × 2 guests × 1 night) €4",
        "City tax (€2.00 × 2 guests × 1 night) €3",
    ),
    ("€101.20", "€100.20"),
    ("€ 97.20", "€ 96.20"),
    ("€ 10.41", "€ 10.42"),
    ("€101.20", "€101.200"),
    ("Final Price", "Service fee €5\nFinal Price"),
    ("Final Price", "City tax (€2.00 × 2 guests × 1 night) €4\nFinal Price"),
    ("Final Price", "Final Price\nFinal Price"),
    ("Additional charges", "Additional charges\nAdditional charges"),
    ("(taxes included)", "(taxes excluded)"),
    ("City tax", "Resort fee"),
    ("2 adults - 1 night, 1 rooms", "2 adults and 1 child - 1 night, 1 rooms"),
    ("2 adults - 1 night, 1 rooms", "2 adults - 1 night, 2 rooms"),
    ("The final price shown is the amount you'll pay to the property.", ""),
    ("based on the maximum occupancy.", "based on the maximum occupancy and extra fees."),
])
def test_additional_charge_layout_rejects_ambiguity_or_unreconciled_components(change):
    facts = _parse(_ADDITIONAL_BODY.replace(*change))
    assert facts is not None
    assert facts["booked_total"] == facts["currency"] == facts["all_in"] == "unknown"


@pytest.mark.parametrize("extra", [
    "This price is approximate.",
    "A cleaning fee is payable separately.",
    "Additional charges\nCity tax €4",
    "The final price shown is the amount you'll pay to the property.",
    "Service fee €5",
    "City tax (€2.00 × 2 guests × 1 night) €4",
])
def test_qualified_charge_block_does_not_override_other_warnings_or_duplicate_statements(extra):
    facts = _parse(_ADDITIONAL_BODY + extra)
    assert facts is not None
    assert facts["all_in"] == "unknown"


def test_city_tax_cannot_be_counted_in_both_subtotal_and_additional_block():
    body = _ADDITIONAL_BODY.replace(
        "Price\n(for 2 guests)", "€2 City tax per person per night €4\nPrice\n(for 2 guests)",
    ).replace("€ 97.20", "€ 101.20").replace("€101.20", "€105.20")
    facts = _parse(body)
    assert facts is not None
    assert facts["all_in"] == "unknown"


@pytest.mark.parametrize("include_final_statement", [False, True])
def test_apartment_additional_tax_contradiction_remains_unknown(include_final_statement):
    body = (
        _ADDITIONAL_BODY.replace("Sat, Oct 24, 2026", "Fri, Oct 30, 2026")
        .replace("2 adults - 1 night, 1 rooms", "2 adults - 1 week, 1 apartment")
        .replace("1 room € 86.79", "1 apartment € 556.36")
        .replace("12 % VAT € 10.41", "10 % VAT € 55.64")
        .replace("€ 97.20", "€ 612")
        .replace(
            "City tax (€2.00 × 2 guests × 1 night) €4", "City tax (€3 × 2 guests × 7 nights) €24",
        )
        .replace("€101.20", "€636")
    )
    if not include_final_statement:
        body = body.replace("The final price shown is the amount you'll pay to the property.", "")
    facts = _parse(body)
    assert facts is not None
    assert facts["adults"] == "2"
    assert facts["booked_total"] == facts["all_in"] == "unknown"


_SPECIAL_REQUESTS_NOTICE = (
    "Guests are required to show a photo ID and credit card upon check-in. "
    "Please note that all Special Requests are subject to availability and additional charges "
    "may apply."
)


def test_exact_optional_special_requests_notice_preserves_reconciled_final_total():
    facts = _parse(_ADDITIONAL_BODY + "\n" + _SPECIAL_REQUESTS_NOTICE)
    assert facts == _parse(_ADDITIONAL_BODY)
    assert facts is not None
    assert (facts["booked_total"], facts["currency"], facts["all_in"]) == (
        "101.20", "EUR", "explicit",
    )


@pytest.mark.parametrize("notice", [
    _SPECIAL_REQUESTS_NOTICE.replace("may apply", "apply"),
    _SPECIAL_REQUESTS_NOTICE.replace("all Special Requests", "all reservations"),
    _SPECIAL_REQUESTS_NOTICE.replace("subject to availability", "mandatory"),
    _SPECIAL_REQUESTS_NOTICE + " Additional charges of €5 are mandatory.",
    _SPECIAL_REQUESTS_NOTICE + "\nService fee €5",
    _SPECIAL_REQUESTS_NOTICE + "\nA mandatory resort fee is payable separately.",
])
def test_optional_notice_exemption_never_hides_other_or_modified_charge_warnings(notice):
    facts = _parse(_ADDITIONAL_BODY + "\n" + notice)
    assert facts is not None
    assert facts["booked_total"] == facts["currency"] == facts["all_in"] == "unknown"


@pytest.mark.parametrize("change", [
    ("€101.20", "€100.20"), ("× 2 guests", "× 3 guests"),
    ("× 1 night", "× 2 nights"), ("€ 10.41", "€ 10.42"),
])
def test_optional_notice_does_not_waive_price_math_or_party_evidence(change):
    facts = _parse(_ADDITIONAL_BODY.replace(*change) + "\n" + _SPECIAL_REQUESTS_NOTICE)
    assert facts is not None
    assert facts["booked_total"] == facts["all_in"] == "unknown"

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


# The dollar confirmation layout, shaped from the affected caller's real page: a refund schedule
# sentence under its own label instead of cost tiers, "US$" amounts, a TAX row, and the total
# closed by "Additional Info" with no final-price statement.
_DOLLAR_BODY = (
    _BODY.replace(
        """Cancellation cost

Free cancellation within: 1 month 9 days
until October 23, 2026 12:00 PM: € 0
from October 23, 2026 12:00 PM: € 100 – Changing the dates of your stay isn't possible.
Cancellation deadlines are in the property's local time.
""",
        "Cancellation policy\tYou can cancel for free until 2 days before arrival.\n"
        "Refund schedule\n"
        "You'll get a full refund if you cancel before 11:59 PM on October 20, 2026. If you "
        "cancel after 12:00 AM on October 21, 2026, you won't be eligible for a refund.\n",
    )
    .replace("1 room\t€ 89.29", "1 room\tUS$309")
    .replace("12 % VAT\t€ 10.71", "12 % TAX\tUS$37.08")
    .replace("€ 2 City tax per person per night\t€ 4\n", "")
    .replace("€ 104", "US$346.08")
    .replace("The final price shown is the amount you'll pay to the property.\n", "")
    + "If you cancel, applicable taxes may still be charged by the property.\n"
)


def _reasons(body: str) -> dict[str, str]:
    reasons: dict[str, str] = {}
    assert parse_confirmation_facts(body, _ANCHORS, observed_at=_NOW, reasons=reasons) is not None
    return reasons


def test_dollar_confirmation_records_its_own_currency_total_and_refund_schedule():
    facts = _parse(_DOLLAR_BODY)
    assert facts is not None
    assert (facts["booked_total"], facts["currency"], facts["all_in"]) == (
        "346.08", "USD", "explicit",
    )
    assert facts["refundability"] == "explicit_refundable"
    assert facts["refund_deadline"] == "2026-10-20"
    assert _reasons(_DOLLAR_BODY) == _reasons(_BODY) == {}


@pytest.mark.parametrize(
    ("other", "currency"),
    [("£", "GBP"), ("US$", "USD"), ("CAD ", "CAD"), ("PLN ", "PLN")],
)
def test_price_and_cancellation_tiers_follow_the_printed_currency(other, currency):
    facts = _parse(_BODY.replace("€ ", other))
    assert facts is not None
    assert (facts["booked_total"], facts["currency"], facts["all_in"]) == (
        "104", currency, "explicit",
    )
    assert facts["refundability"] == "explicit_refundable"


def test_grouped_thousands_total_is_read_as_one_amount():
    body = (
        _BODY.replace("1 room\t€ 89.29", "1 room\t€ 1,000.00")
        .replace("12 % VAT\t€ 10.71", "12 % VAT\t€ 120.00")
        .replace("€ 104", "€ 1,124.00")
    )
    facts = _parse(body)
    assert facts is not None
    assert (facts["booked_total"], facts["currency"]) == ("1124.00", "EUR")


@pytest.mark.parametrize(
    ("change", "reasons"),
    [
        (("US$346.08", "346.08"), {"booked_total": "total_not_money"}),
        # A bare dollar sign names no single currency.
        (("US$346.08", "$346.08"), {"booked_total": "total_not_money"}),
        (("US$346.08", "XYZ 346.08"), {"booked_total": "total_not_money"}),
        (("US$346.08", "US$346,08"), {"booked_total": "total_not_money"}),
        (("1 room\tUS$309", "1 room\t€ 309"), {"booked_total": "mixed_currency"}),
        (("12 % TAX\tUS$37.08", "12 % TAX\tCAD 37.08"), {"booked_total": "tax_row"}),
        (("12 % TAX\tUS$37.08", "12 % TAX\tUS$37.00"), {"booked_total": "tax_row"}),
        (("12 % TAX\tUS$37.08", "Resort fee\tUS$37.08"),
         {"booked_total": "unrecognized_component_row"}),
        # Without the page's final-price statement, only a reconciled tax row proves all-in.
        (("1 room\tUS$309\n12 % TAX\tUS$37.08", "1 room\tUS$346.08"),
         {"booked_total": "tax_inclusion_unproven"}),
        (("(for 2 guests)\n", ""), {"booked_total": "final_price_statement"}),
        (("Additional Info\n", "Good to know\n"), {"booked_total": "final_price_statement"}),
        (("you won't be eligible for a refund.", "you'll get a partial refund."),
         {"refundability": "refund_schedule_unrecognized"}),
        (("cancel after 12:00 AM on October 21", "cancel after 12:00 AM on October 22"),
         {"refundability": "cutoffs_not_adjacent"}),
        (("before 11:59 PM", "before 13:59 PM"),
         {"refundability": "refund_schedule_unrecognized"}),
        (("Refund schedule\n", "Refund schedule\nRefund schedule\n"),
         {"refundability": "refund_schedule_unrecognized"}),
        (("Refund schedule\n", "Refund policy\n"),
         {"refundability": "no_cancellation_evidence"}),
    ],
)
def test_unknown_total_or_refundability_names_the_rule_that_stopped_it(change, reasons):
    body = _DOLLAR_BODY.replace(*change)
    assert body != _DOLLAR_BODY
    facts = _parse(body)
    assert facts is not None
    assert _reasons(body) == reasons
    if "booked_total" in reasons:
        assert (facts["booked_total"], facts["all_in"]) == ("unknown", "unknown")
    if "refundability" in reasons:
        assert facts["refundability"] == "unknown"


def test_unknown_fact_reasons_never_carry_page_content():
    reasons = _reasons(_DOLLAR_BODY.replace("US$346.08", "346.08 secret"))
    assert reasons and all(value.replace("_", "").isalpha() for value in reasons.values())


def test_cancellation_tiers_in_two_currencies_are_insufficient():
    assert _reasons(_BODY.replace("PM: € 100", "PM: US$100")) == {
        "refundability": "cost_tiers_unrecognized",
    }


def test_refund_schedule_beside_its_label_and_expired_schedule():
    inline = _parse(_DOLLAR_BODY.replace("Refund schedule\n", "Refund schedule\t"))
    assert inline is not None and inline["refund_deadline"] == "2026-10-20"
    expired = _parse(_DOLLAR_BODY, now=datetime(2026, 10, 22, 13, tzinfo=UTC))
    assert expired is not None
    assert expired["refundability"] == "explicit_nonrefundable"


def test_rendered_cost_tiers_outrank_a_refund_schedule_sentence():
    # A page that prints cost tiers is judged by them alone, even when they do not qualify.
    body = _BODY.replace(
        "from October 23, 2026 12:00 PM: € 100 – Changing the dates of your stay isn't possible.\n",
        "",
    ).replace(
        "1 room\t€ 89.29",
        "Refund schedule\nYou'll get a full refund if you cancel before 11:59 PM on "
        "October 20, 2026. If you cancel after 12:00 AM on October 21, 2026, you won't be "
        "eligible for a refund.\n1 room\t€ 89.29",
    )
    assert _reasons(body) == {"refundability": "cost_tiers_unrecognized"}


def test_euro_page_without_its_statement_needs_the_same_closed_shape_and_tax_row():
    without = _BODY.replace("The final price shown is the amount you'll pay to the property.\n", "")
    facts = _parse(without)
    assert facts is not None and (facts["booked_total"], facts["currency"]) == ("104", "EUR")
    assert _reasons(without.replace("12 % VAT\t€ 10.71\n", "").replace("€ 89.29", "€ 100")) == {
        "booked_total": "tax_inclusion_unproven",
    }
