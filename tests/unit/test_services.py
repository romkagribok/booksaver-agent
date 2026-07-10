from datetime import date
from decimal import Decimal

import pytest

from booksaver.domain.errors import BookingRejectedError, LocalPathViolation
from booksaver.domain.models import Booking
from booksaver.domain.services import BookingRegistrationService, LocalOnlyDataPolicy
from booksaver.domain.value_objects import (
    ConfirmationId,
    DataDirectory,
    Money,
    Occupancy,
    Platform,
    ProductType,
    Property,
    RefundabilityPolicy,
    RoomType,
    StayDates,
)


def _valid_inputs() -> dict:
    return dict(
        platform=Platform.BOOKING_COM,
        product_type=ProductType.HOTEL,
        confirmation_id=ConfirmationId.of("BKG-TEST"),
        property=Property(name="Hotel Test", booking_com_ref="ref_123"),
        stay_dates=StayDates(date(2026, 9, 1), date(2026, 9, 5)),
        room_type=RoomType(label="Standard"),
        baseline_price=Money.of("200.00", "EUR"),
        refundability=RefundabilityPolicy(is_refundable=True, note="Free cancellation"),
        occupancy=Occupancy(adults=2),
        exists_fn=lambda _: False,
    )


class TestBookingRegistrationService:
    def test_valid_registration_returns_booking_and_event(self):
        service = BookingRegistrationService()
        booking, event = service.register(**_valid_inputs())
        assert isinstance(booking, Booking)
        assert booking.confirmation_id.value == "BKG-TEST"
        assert booking.baseline_price == Money.of("200.00", "EUR")
        assert event.booking_id == booking.booking_id

    def test_not_refundable_rejected(self):
        service = BookingRegistrationService()
        inputs = _valid_inputs()
        inputs["refundability"] = RefundabilityPolicy(is_refundable=False, note="Non-refundable")
        with pytest.raises(BookingRejectedError, match="refundable"):
            service.register(**inputs)

    def test_duplicate_confirmation_rejected(self):
        service = BookingRegistrationService()
        inputs = _valid_inputs()
        inputs["exists_fn"] = lambda _: True
        with pytest.raises(BookingRejectedError, match="already registered"):
            service.register(**inputs)

    def test_booking_id_is_unique_per_call(self):
        service = BookingRegistrationService()
        b1, _ = service.register(**_valid_inputs())
        inputs2 = _valid_inputs()
        inputs2["confirmation_id"] = ConfirmationId.of("BKG-OTHER")
        b2, _ = service.register(**inputs2)
        assert b1.booking_id != b2.booking_id

    def test_baseline_price_recorded(self):
        service = BookingRegistrationService()
        booking, _ = service.register(**_valid_inputs())
        assert booking.baseline_price.amount == Decimal("200.00")
        assert booking.baseline_price.currency == "EUR"

    def test_registered_at_is_set(self):
        service = BookingRegistrationService()
        booking, _ = service.register(**_valid_inputs())
        assert booking.registered_at is not None

    # Platform and product-type rejection guards exist in BookingRegistrationService but
    # cannot be triggered via the MVP enums (Platform has only BOOKING_COM, ProductType
    # only HOTEL). They are forward-compatibility guards for when more values are added.


class TestLocalOnlyDataPolicy:
    def test_path_inside_data_dir_accepted(self, tmp_path):
        data_dir = DataDirectory.of(str(tmp_path))
        policy = LocalOnlyDataPolicy(data_dir)
        policy.assert_local(tmp_path / "booksaver.db")  # must not raise

    def test_path_outside_data_dir_rejected(self, tmp_path):
        data_dir = DataDirectory.of(str(tmp_path / "booksaver"))
        policy = LocalOnlyDataPolicy(data_dir)
        with pytest.raises(LocalPathViolation):
            policy.assert_local(tmp_path / "other" / "file.db")

    def test_exact_data_dir_path_accepted(self, tmp_path):
        data_dir = DataDirectory.of(str(tmp_path))
        policy = LocalOnlyDataPolicy(data_dir)
        policy.assert_local(tmp_path)  # the dir itself — must not raise
