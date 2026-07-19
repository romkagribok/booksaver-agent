from dataclasses import replace

import pytest

from booksaver.application.post_rebook import (
    canonicalize_booking_property_ref,
    replacement_booking,
    replacement_facts,
)
from booksaver.domain.models import BookingStatus
from booksaver.domain.value_objects import Money, Property

from .monitor.fakes import make_booking

SOURCE_URL = (
    "https://www.booking.com/hotel/us/example-hotel.html?aid=304142&sid=secret"
)


def _source_booking():
    return replace(
        make_booking(),
        property=Property(name="Example Hotel", booking_com_ref=SOURCE_URL),
    )


def test_property_ref_is_same_property_and_tracking_free() -> None:
    assert canonicalize_booking_property_ref(
        "https://booking.com/hotel/us/example-hotel.html?checkin=2026-10-01#rooms",
        SOURCE_URL,
    ) == "https://www.booking.com/hotel/us/example-hotel.html"


@pytest.mark.parametrize(
    "value",
    [
        "http://www.booking.com/hotel/us/example-hotel.html",
        "https://evil.example/hotel/us/example-hotel.html",
        "https://www.booking.com/searchresults.html",
        "not a url",
    ],
)
def test_property_ref_rejects_non_property_booking_urls(value: str) -> None:
    with pytest.raises(ValueError, match="HTTPS Booking.com property URL"):
        canonicalize_booking_property_ref(value, SOURCE_URL)


def test_property_ref_rejects_a_different_property() -> None:
    with pytest.raises(ValueError, match="different Booking.com property"):
        canonicalize_booking_property_ref(
            "https://www.booking.com/hotel/us/other-hotel.html", SOURCE_URL
        )


def test_replacement_uses_actual_checkout_total_not_detected_offer() -> None:
    source = _source_booking()
    facts = replacement_facts(
        "NEW-123",
        "https://www.booking.com/hotel/us/example-hotel.html?aid=1",
        "387.42 USD",
        source,
    )

    replacement = replacement_booking(source, facts)

    assert replacement.booking_id == source.booking_id
    assert replacement.baseline_price == Money.of("387.42", "USD")
    assert replacement.baseline_price != Money.of("350", "EUR")
    assert replacement.status is BookingStatus.ACTIVE
    assert replacement.stay_dates == source.stay_dates
    assert replacement.room_type == source.room_type
    assert replacement.refundability == source.refundability
    assert replacement.occupancy == source.occupancy


def test_replacement_facts_require_amount_and_currency() -> None:
    with pytest.raises(ValueError, match="amount CURRENCY"):
        replacement_facts("NEW-123", SOURCE_URL, "387.42", _source_booking())
