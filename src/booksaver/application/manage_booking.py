from __future__ import annotations

from booksaver.domain.errors import BookingRejectedError
from booksaver.domain.models import Booking

from .ports import BookingRepository


def update_booking(repo: BookingRepository, booking: Booking) -> None:
    """Persist a validated booking aggregate without changing its identity.

    Confirmation IDs are globally unique in schema v8. Registration checks that
    invariant before insert; editing needs the equivalent check while allowing a
    booking to retain its own confirmation ID.
    """
    conflict = repo.get_by_confirmation(booking.confirmation_id)
    if conflict is not None and conflict.booking_id != booking.booking_id:
        raise BookingRejectedError(
            f"Booking confirmation '{booking.confirmation_id.value}' is already registered"
        )
    repo.update(booking)


def delete_booking(repo: BookingRepository, booking_id: str) -> bool:
    """Permanently remove one local booking and its repository-owned history."""
    return repo.delete(booking_id)
