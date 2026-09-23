from __future__ import annotations

import pytest

from booksaver.domain.browser_executor import english_booking_property_identity


@pytest.mark.parametrize(
    "url",
    [
        "https://www.booking.com/hotel/us/the-union-club.html",
        "https://www.booking.com/hotel/us/the-union-club.en-us.html",
        "https://www.booking.com/hotel/us/the-union-club.en-gb.html",
        "https://secure.booking.com/hotel/us/the-union-club.html",
    ],
)
def test_locale_variants_name_one_hotel(url: str) -> None:
    identity = english_booking_property_identity(url)
    assert identity is not None
    assert identity[1:] == ("us", "the-union-club")


@pytest.mark.parametrize(
    "url",
    [
        "https://www.booking.com/hotel/us/the-union-club.de.html",
        "http://www.booking.com/hotel/us/the-union-club.html",
        "https://evil.example/hotel/us/the-union-club.html",
        "hotel-id-12345",
    ],
)
def test_unrecognized_references_have_no_identity(url: str) -> None:
    assert english_booking_property_identity(url) is None


def test_different_slugs_are_different_hotels() -> None:
    assert english_booking_property_identity(
        "https://www.booking.com/hotel/us/a.html"
    ) != english_booking_property_identity("https://www.booking.com/hotel/us/b.en-us.html")
