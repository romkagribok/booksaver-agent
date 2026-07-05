from __future__ import annotations

from decimal import Decimal

from booksaver.domain.value_objects import Money
from booksaver.infrastructure.llm.anthropic_adapter import parse_extraction_response
from booksaver.monitor.dom_extract import extract_from_text

# ── DOM extraction ────────────────────────────────────────────────────────────

def test_extracts_euro_total() -> None:
    result = extract_from_text("Room details\nTotal price: € 1,234.56\nThanks")
    assert result.price == Money(amount=Decimal("1234.56"), currency="EUR")
    assert result.confidence >= 0.5


def test_extracts_currency_code_format() -> None:
    result = extract_from_text("Total: EUR 380.00")
    assert result.price == Money(amount=Decimal("380.00"), currency="EUR")


def test_extracts_european_decimal_style() -> None:
    result = extract_from_text("Total price: 1.234,56 €")
    assert result.price == Money(amount=Decimal("1234.56"), currency="EUR")


def test_ignores_prices_without_total_context() -> None:
    # A price with no "total" hint nearby should not be trusted
    result = extract_from_text("Upgrade to suite for € 999.00 per night")
    assert result.price is None
    assert result.confidence == 0.0


def test_detects_refundable() -> None:
    result = extract_from_text("Free cancellation before Sep 1\nTotal price: € 100.00")
    assert result.is_refundable is True


def test_detects_non_refundable() -> None:
    result = extract_from_text("This rate is non-refundable\nTotal price: € 100.00")
    assert result.is_refundable is False


def test_refundability_unknown_when_no_hints() -> None:
    result = extract_from_text("Total price: € 100.00")
    assert result.is_refundable is None


def test_empty_page_yields_nothing() -> None:
    result = extract_from_text("")
    assert result.price is None
    assert result.confidence == 0.0


# ── LLM response parsing ──────────────────────────────────────────────────────

def test_parses_clean_json_reply() -> None:
    raw = (
        '{"price": "350.00", "currency": "EUR", "is_refundable": true,'
        ' "cancellation_deadline": "until 1 Sep", "confidence": 0.9}'
    )
    result = parse_extraction_response(raw)
    assert result.price == Money(amount=Decimal("350.00"), currency="EUR")
    assert result.is_refundable is True
    assert result.cancellation_deadline_raw == "until 1 Sep"
    assert result.confidence == 0.9


def test_parses_json_wrapped_in_prose() -> None:
    raw = 'Here is the data: {"price": "100", "currency": "USD", "confidence": 0.7} Done.'
    result = parse_extraction_response(raw)
    assert result.price == Money(amount=Decimal("100"), currency="USD")


def test_no_json_yields_zero_confidence() -> None:
    result = parse_extraction_response("I could not find a price on this page.")
    assert result.price is None
    assert result.confidence == 0.0


def test_malformed_json_yields_zero_confidence() -> None:
    result = parse_extraction_response('{"price": "100", "currency":')
    assert result.price is None
    assert result.confidence == 0.0


def test_null_price_handled() -> None:
    raw = '{"price": null, "currency": null, "is_refundable": null, "confidence": 0.2}'
    result = parse_extraction_response(raw)
    assert result.price is None
    assert result.is_refundable is None


def test_invalid_currency_dropped() -> None:
    raw = '{"price": "100", "currency": "???", "confidence": 0.9}'
    result = parse_extraction_response(raw)
    assert result.price is None  # Money.of rejects bad currency


def test_out_of_range_confidence_clamped() -> None:
    raw = '{"price": "100", "currency": "EUR", "confidence": 5.0}'
    result = parse_extraction_response(raw)
    assert result.confidence == 0.5  # fallback for present price
