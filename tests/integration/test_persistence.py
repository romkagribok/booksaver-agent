from datetime import date
from decimal import Decimal

import pytest

from booksaver.application.register_booking import register_booking
from booksaver.domain.errors import BookingRejectedError
from booksaver.domain.models import BookingStatus
from booksaver.domain.value_objects import (
    ConfirmationId,
    Money,
    Occupancy,
    Platform,
    ProductType,
    Property,
    RefundabilityPolicy,
    RoomType,
    StayDates,
)
from booksaver.infrastructure.persistence.sqlite_store import (
    SqliteBookingRepository,
    SqliteStore,
)


@pytest.fixture
def store(tmp_path):
    with SqliteStore(tmp_path / "booksaver.db") as s:
        yield s


@pytest.fixture
def repo(store):
    return SqliteBookingRepository(store)


def _make_booking(confirmation: str = "BKG-001") -> dict:
    return dict(
        platform=Platform.BOOKING_COM,
        product_type=ProductType.HOTEL,
        confirmation_id=ConfirmationId.of(confirmation),
        property=Property(name="Grand Hotel", booking_com_ref="grand_ref"),
        stay_dates=StayDates(date(2026, 10, 1), date(2026, 10, 5)),
        room_type=RoomType(label="Deluxe Double"),
        baseline_price=Money.of("350.00", "EUR"),
        refundability=RefundabilityPolicy(is_refundable=True, note="Free cancellation"),
        occupancy=Occupancy(adults=2),
    )


class TestSqliteBookingRepository:
    def test_add_and_get_by_id(self, repo):
        booking, _ = register_booking(repo=repo, **_make_booking())
        fetched = repo.get_by_id(booking.booking_id)
        assert fetched is not None
        assert fetched.booking_id == booking.booking_id

    def test_get_by_confirmation(self, repo):
        booking, _ = register_booking(repo=repo, **_make_booking("BKG-CONF"))
        fetched = repo.get_by_confirmation(ConfirmationId.of("BKG-CONF"))
        assert fetched is not None
        assert fetched.confirmation_id.value == "BKG-CONF"

    def test_exists_true_after_add(self, repo):
        register_booking(repo=repo, **_make_booking("BKG-EXISTS"))
        assert repo.exists(ConfirmationId.of("BKG-EXISTS")) is True

    def test_exists_false_before_add(self, repo):
        assert repo.exists(ConfirmationId.of("BKG-NOPE")) is False

    def test_list_active_returns_active_only(self, repo):
        register_booking(repo=repo, **_make_booking("BKG-A"))
        register_booking(repo=repo, **_make_booking("BKG-B"))
        active = repo.list_active()
        assert len(active) == 2
        assert all(b.status == BookingStatus.ACTIVE for b in active)

    def test_duplicate_confirmation_rejected(self, repo):
        register_booking(repo=repo, **_make_booking("BKG-DUP"))
        with pytest.raises(BookingRejectedError, match="already registered"):
            register_booking(repo=repo, **_make_booking("BKG-DUP"))

    def test_round_trip_preserves_all_fields(self, repo):
        inputs = _make_booking("BKG-ROUNDTRIP")
        booking, _ = register_booking(repo=repo, **inputs)
        fetched = repo.get_by_id(booking.booking_id)

        assert fetched is not None
        assert fetched.platform == Platform.BOOKING_COM
        assert fetched.product_type == ProductType.HOTEL
        assert fetched.confirmation_id.value == "BKG-ROUNDTRIP"
        assert fetched.property.name == "Grand Hotel"
        assert fetched.property.booking_com_ref == "grand_ref"
        assert fetched.stay_dates.check_in == date(2026, 10, 1)
        assert fetched.stay_dates.check_out == date(2026, 10, 5)
        assert fetched.room_type.label == "Deluxe Double"
        assert fetched.baseline_price.amount == Decimal("350.00")
        assert fetched.baseline_price.currency == "EUR"
        assert fetched.refundability.is_refundable is True
        assert fetched.status == BookingStatus.ACTIVE

    def test_money_stored_as_decimal_not_float(self, repo, store):
        register_booking(repo=repo, **_make_booking("BKG-DECIMAL"))
        row = store.conn.execute(
            "SELECT baseline_amount FROM bookings WHERE confirmation_id = ?",
            ("BKG-DECIMAL",),
        ).fetchone()
        # Must be a string in the DB, never a float
        assert isinstance(row["baseline_amount"], str)
        assert Decimal(row["baseline_amount"]) == Decimal("350.00")

    def test_get_by_id_returns_none_for_unknown(self, repo):
        assert repo.get_by_id("nonexistent-uuid") is None

    def test_get_by_confirmation_returns_none_for_unknown(self, repo):
        assert repo.get_by_confirmation(ConfirmationId.of("BKG-UNKNOWN")) is None
