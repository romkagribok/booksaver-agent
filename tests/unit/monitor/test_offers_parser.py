from __future__ import annotations

from decimal import Decimal

from booksaver.infrastructure.llm.anthropic_adapter import parse_offers_response

_VALID = """\
Here are the offers:
[{"room_label": "Standard Double", "price": "350.00", "currency": "EUR",
  "is_refundable": true, "cancellation_text": "Free cancellation",
  "matches_room": true, "match_confidence": 0.9},
 {"room_label": "Deluxe Suite", "price": "520.00", "currency": "EUR",
  "is_refundable": false, "cancellation_text": null,
  "matches_room": false, "match_confidence": 0.1}]
"""


class TestParseOffersResponse:
    def test_valid_array_parsed(self):
        offers = parse_offers_response(_VALID)
        assert len(offers) == 2
        first = offers[0]
        assert first.room_label == "Standard Double"
        assert first.total.amount == Decimal("350.00")
        assert first.total.currency == "EUR"
        assert first.is_refundable is True
        assert first.matches_room is True
        assert first.match_confidence == 0.9

    def test_no_json_array_yields_empty(self):
        assert parse_offers_response("I could not find any offers.") == []

    def test_malformed_json_yields_empty(self):
        assert parse_offers_response("[{'room_label': broken}]") == []

    def test_non_list_json_yields_empty(self):
        assert parse_offers_response('{"room_label": "X"}') == []

    def test_offer_with_unparseable_price_skipped(self):
        raw = (
            '[{"room_label": "A", "price": "n/a", "currency": "EUR",'
            ' "matches_room": true, "match_confidence": 0.9},'
            ' {"room_label": "B", "price": "100.00", "currency": "EUR",'
            ' "matches_room": true, "match_confidence": 0.9}]'
        )
        offers = parse_offers_response(raw)
        assert [o.room_label for o in offers] == ["B"]

    def test_missing_label_skipped(self):
        raw = '[{"price": "100.00", "currency": "EUR", "matches_room": true}]'
        assert parse_offers_response(raw) == []

    def test_out_of_range_confidence_becomes_zero(self):
        raw = (
            '[{"room_label": "A", "price": "100.00", "currency": "EUR",'
            ' "matches_room": true, "match_confidence": 1.7}]'
        )
        [offer] = parse_offers_response(raw)
        assert offer.match_confidence == 0.0

    def test_non_bool_refundability_becomes_none(self):
        raw = (
            '[{"room_label": "A", "price": "100.00", "currency": "EUR",'
            ' "is_refundable": "yes", "matches_room": true, "match_confidence": 0.9}]'
        )
        [offer] = parse_offers_response(raw)
        assert offer.is_refundable is None
