from __future__ import annotations

from decimal import Decimal

from booksaver.monitor.room_table import has_confident_exact_match, parse_candidates

from .fakes import make_booking

_ROOM_TABLE_TEXT = """\
Availability
Select your room

Standard Double
Max persons: 2
€ 350.00
Free cancellation before 30 August 2026

Deluxe Suite
Max persons: 3
€ 520.00
Non-refundable

Twin Room
Max persons: 2
€ 310.00
"""


class TestParseCandidates:
    def test_finds_room_blocks_with_prices(self):
        candidates = parse_candidates(_ROOM_TABLE_TEXT, make_booking())
        labels = [c.room_label for c in candidates]
        assert "Standard Double" in labels
        assert "Deluxe Suite" in labels
        assert "Twin Room" in labels

    def test_exact_label_match_flagged_with_full_confidence(self):
        candidates = parse_candidates(_ROOM_TABLE_TEXT, make_booking())
        standard = next(c for c in candidates if c.room_label == "Standard Double")
        assert standard.matches_room
        assert standard.match_confidence == 1.0
        assert standard.total.amount == Decimal("350.00")
        assert standard.total.currency == "EUR"
        assert standard.is_refundable is True
        assert "Free cancellation" in standard.cancellation_text

    def test_non_exact_labels_never_matched_by_dom(self):
        candidates = parse_candidates(_ROOM_TABLE_TEXT, make_booking())
        suite = next(c for c in candidates if c.room_label == "Deluxe Suite")
        assert not suite.matches_room
        assert suite.match_confidence == 0.0
        assert suite.is_refundable is False

    def test_room_without_refund_wording_has_unknown_refundability(self):
        candidates = parse_candidates(_ROOM_TABLE_TEXT, make_booking())
        twin = next(c for c in candidates if c.room_label == "Twin Room")
        assert twin.is_refundable is None

    def test_room_line_without_nearby_price_is_skipped(self):
        text = "Standard Double\nMax persons: 2\nGreat view\nBreakfast included"
        assert parse_candidates(text, make_booking()) == []

    def test_empty_text_yields_no_candidates(self):
        assert parse_candidates("", make_booking()) == []


class TestConfidentExactMatch:
    def test_true_when_booked_room_parsed_with_refundability(self):
        candidates = parse_candidates(_ROOM_TABLE_TEXT, make_booking())
        assert has_confident_exact_match(candidates, make_booking())

    def test_false_when_booked_room_missing(self):
        text = "Deluxe Suite\n€ 520.00\nNon-refundable"
        candidates = parse_candidates(text, make_booking())
        assert not has_confident_exact_match(candidates, make_booking())

    def test_false_when_refundability_not_stated(self):
        text = "Standard Double\n€ 350.00\nMax persons: 2"
        candidates = parse_candidates(text, make_booking())
        assert not has_confident_exact_match(candidates, make_booking())
