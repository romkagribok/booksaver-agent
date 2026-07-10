from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from .errors import BookingRejectedError, LocalPathViolation
from .events import BookingRegistered
from .models import Booking
from .value_objects import (
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


class BookingRegistrationService:
    def register(
        self,
        platform: Platform,
        product_type: ProductType,
        confirmation_id: ConfirmationId,
        property: Property,
        stay_dates: StayDates,
        room_type: RoomType,
        baseline_price: Money,
        refundability: RefundabilityPolicy,
        occupancy: Occupancy,
        exists_fn: Callable[[ConfirmationId], bool],
    ) -> tuple[Booking, BookingRegistered]:
        if platform != Platform.BOOKING_COM:
            raise BookingRejectedError("Only Booking.com bookings are supported in MVP.")
        if product_type != ProductType.HOTEL:
            raise BookingRejectedError("Only hotel bookings are supported in MVP.")
        if not refundability.is_refundable:
            raise BookingRejectedError("Only refundable bookings can be registered.")
        if exists_fn(confirmation_id):
            raise BookingRejectedError(
                f"Booking '{confirmation_id.value}' is already registered."
            )

        now = datetime.now(UTC)
        booking = Booking.create(
            platform=platform,
            product_type=product_type,
            confirmation_id=confirmation_id,
            property=property,
            stay_dates=stay_dates,
            room_type=room_type,
            baseline_price=baseline_price,
            refundability=refundability,
            registered_at=now,
            occupancy=occupancy,
        )
        event = BookingRegistered(
            booking_id=booking.booking_id,
            platform=platform.value,
            property=property,
            stay_dates=stay_dates,
            room_type=room_type,
            baseline_price=baseline_price,
            registered_at=now,
        )
        return booking, event


class LocalOnlyDataPolicy:
    def __init__(self, data_directory: DataDirectory) -> None:
        self._data_dir = data_directory

    def assert_local(self, target_path: Path) -> None:
        try:
            target_path.relative_to(self._data_dir.path)
        except ValueError:
            raise LocalPathViolation(str(target_path), str(self._data_dir.path))
