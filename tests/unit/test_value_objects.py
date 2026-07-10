from datetime import date, timedelta
from decimal import Decimal

import pytest

from booksaver.domain.value_objects import (
    CheckInterval,
    ConfirmationId,
    DataDirectory,
    Money,
    RefundabilityPolicy,
    StayDates,
)


class TestMoney:
    def test_valid(self):
        m = Money(amount=Decimal("100.00"), currency="EUR")
        assert m.amount == Decimal("100.00")
        assert m.currency == "EUR"

    def test_zero_amount_allowed(self):
        Money(amount=Decimal("0"), currency="USD")

    def test_negative_amount_rejected(self):
        with pytest.raises(ValueError, match="non-negative"):
            Money(amount=Decimal("-1"), currency="EUR")

    def test_invalid_currency_rejected(self):
        with pytest.raises(ValueError, match="ISO-4217"):
            Money(amount=Decimal("10"), currency="eu")

    def test_numeric_currency_rejected(self):
        with pytest.raises(ValueError, match="ISO-4217"):
            Money(amount=Decimal("10"), currency="123")

    def test_equality_by_value(self):
        assert Money(Decimal("50"), "EUR") == Money(Decimal("50"), "EUR")

    def test_inequality(self):
        assert Money(Decimal("50"), "EUR") != Money(Decimal("51"), "EUR")

    def test_of_normalises_currency(self):
        m = Money.of("99.99", "eur")
        assert m.currency == "EUR"

    def test_of_rejects_invalid_amount(self):
        with pytest.raises(ValueError):
            Money.of("not-a-number", "EUR")


class TestStayDates:
    def test_valid(self):
        sd = StayDates(date(2026, 9, 1), date(2026, 9, 5))
        assert sd.check_in == date(2026, 9, 1)

    def test_same_day_rejected(self):
        with pytest.raises(ValueError, match="after"):
            StayDates(date(2026, 9, 1), date(2026, 9, 1))

    def test_check_out_before_check_in_rejected(self):
        with pytest.raises(ValueError, match="after"):
            StayDates(date(2026, 9, 5), date(2026, 9, 1))

    def test_equality_by_value(self):
        assert StayDates(date(2026, 1, 1), date(2026, 1, 3)) == StayDates(
            date(2026, 1, 1), date(2026, 1, 3)
        )


class TestConfirmationId:
    def test_valid(self):
        c = ConfirmationId.of("BKG-123")
        assert c.value == "BKG-123"

    def test_strips_whitespace(self):
        c = ConfirmationId.of("  BKG-123  ")
        assert c.value == "BKG-123"

    def test_empty_rejected(self):
        with pytest.raises(ValueError):
            ConfirmationId.of("")

    def test_whitespace_only_rejected(self):
        with pytest.raises(ValueError):
            ConfirmationId.of("   ")

    def test_direct_construction_empty_rejected(self):
        with pytest.raises(ValueError):
            ConfirmationId(value="")


class TestCheckInterval:
    def test_parse_hours(self):
        ci = CheckInterval.parse("6h")
        assert ci.duration == timedelta(hours=6)
        assert str(ci) == "6h"

    def test_parse_minutes(self):
        ci = CheckInterval.parse("30m")
        assert ci.duration == timedelta(minutes=30)
        assert str(ci) == "30m"

    def test_parse_days(self):
        ci = CheckInterval.parse("1d")
        assert ci.duration == timedelta(days=1)
        assert str(ci) == "1d"

    def test_minimum_enforced(self):
        with pytest.raises(ValueError, match="15m"):
            CheckInterval.parse("14m")

    def test_exactly_minimum_allowed(self):
        CheckInterval.parse("15m")

    def test_zero_rejected(self):
        with pytest.raises(ValueError):
            CheckInterval(duration=timedelta(0))

    def test_invalid_format_rejected(self):
        with pytest.raises(ValueError, match="Invalid interval"):
            CheckInterval.parse("2hours")

    def test_equality(self):
        assert CheckInterval.parse("6h") == CheckInterval.parse("6h")


class TestDataDirectory:
    def test_valid_local_path(self, tmp_path):
        dd = DataDirectory.of(str(tmp_path))
        assert dd.path == tmp_path.resolve()

    def test_tilde_expansion(self):
        dd = DataDirectory.of("~/.booksaver")
        assert "~" not in str(dd.path)

    def test_url_rejected(self):
        with pytest.raises(ValueError, match="local path"):
            DataDirectory.of("https://example.com/data")

    def test_equality(self, tmp_path):
        assert DataDirectory.of(str(tmp_path)) == DataDirectory.of(str(tmp_path))


class TestRefundabilityPolicy:
    def test_refundable(self):
        r = RefundabilityPolicy(is_refundable=True, note="Free cancellation until Aug 1")
        assert r.is_refundable is True

    def test_with_deadline(self):
        r = RefundabilityPolicy(
            is_refundable=True,
            note="Until Aug 1",
            deadline=date(2026, 8, 1),
        )
        assert r.deadline == date(2026, 8, 1)

    def test_equality_by_value(self):
        r1 = RefundabilityPolicy(True, "note")
        r2 = RefundabilityPolicy(True, "note")
        assert r1 == r2
