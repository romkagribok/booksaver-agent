from __future__ import annotations

from booksaver.domain.events import BookingRegistered
from booksaver.domain.models import Booking
from booksaver.domain.services import BookingRegistrationService
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

from .ports import BookingRepository


def register_booking(
    repo: BookingRepository,
    platform: Platform,
    product_type: ProductType,
    confirmation_id: ConfirmationId,
    property: Property,
    stay_dates: StayDates,
    room_type: RoomType,
    baseline_price: Money,
    refundability: RefundabilityPolicy,
    occupancy: Occupancy,
) -> tuple[Booking, BookingRegistered]:
    service = BookingRegistrationService()
    booking, event = service.register(
        platform=platform,
        product_type=product_type,
        confirmation_id=confirmation_id,
        property=property,
        stay_dates=stay_dates,
        room_type=room_type,
        baseline_price=baseline_price,
        refundability=refundability,
        occupancy=occupancy,
        exists_fn=repo.exists,
    )
    repo.add(booking)
    return booking, event
