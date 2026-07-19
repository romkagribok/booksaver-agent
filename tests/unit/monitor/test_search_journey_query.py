from __future__ import annotations

from dataclasses import replace
from urllib.parse import parse_qs, urlparse

from booksaver.domain.value_objects import Occupancy, Property
from booksaver.monitor.search_journey import _search_results_url

from .fakes import make_booking


class TestTrustedSearchQuery:
    def test_uses_persisted_property_dates_and_occupancy(self):
        booking = replace(
            make_booking(),
            property=Property(
                name="Hôtel Test & Spa",
                booking_com_ref=make_booking().property.booking_com_ref,
            ),
            occupancy=Occupancy(adults=3, children=2, rooms=2),
        )

        query = parse_qs(urlparse(_search_results_url(booking)).query)

        assert query["ss"] == ["Hôtel Test & Spa"]
        assert query["checkin"] == ["2026-09-01"]
        assert query["checkout"] == ["2026-09-05"]
        assert query["group_adults"] == ["3"]
        assert query["group_children"] == ["2"]
        assert query["no_rooms"] == ["2"]
        assert query["selected_currency"] == ["EUR"]

    def test_optional_booking_destination_identity_is_preserved(self):
        query = parse_qs(
            urlparse(
                _search_results_url(
                    make_booking(), dest_id="12345", dest_type="hotel"
                )
            ).query
        )

        assert query["dest_id"] == ["12345"]
        assert query["dest_type"] == ["hotel"]
