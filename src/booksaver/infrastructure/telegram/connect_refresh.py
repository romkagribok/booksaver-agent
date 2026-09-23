"""Explain the background inventory refresh that follows a saved login."""

from collections.abc import Callable

from booksaver.daemon.check_coordinator import (
    CheckCoordinator,
    ImmediateAdmission,
    InventoryCompletion,
)
from booksaver.domain.account_sync import SynchronizationTrigger

from .inventory_messages import empty_upcoming_message, refresh_failure_guidance


def start_post_connect_refresh(
    telegram_user_id: int,
    coordinator: CheckCoordinator,
    send: Callable[[int, str], object],
) -> None:
    # Announce before admission: even an immediately completed worker must not send
    # its result before this progress message. Authentication was already announced.
    send(
        telegram_user_id,
        "Loading your reservations from Booking.com. "
        "I'll send the result here.",
    )

    def completed(completion: InventoryCompletion) -> None:
        report = completion.report
        if report is not None and report.upcoming_empty_observed:
            message = empty_upcoming_message(has_saved=bool(completion.reservations))
        elif report is not None and (report.succeeded or report.accepted_positive_observations):
            preserved = (
                " Other saved reservations were kept."
                if report.accepted_positive_observations
                else ""
            )
            message = (
                f"Found {report.discovered} reservation{'s' if report.discovered != 1 else ''}. "
                f"We can check prices for {report.eligible} of them.{preserved} "
                "Send /checknow to check prices, or /bookings for details."
            )
        else:
            message = (
                "Your Booking.com login was saved, but we couldn't load your reservations. "
                "Your saved reservations are still here. "
                + refresh_failure_guidance(report.failure_code if report is not None else None)
            )
        send(telegram_user_id, message)

    admission = coordinator.request_inventory(
        telegram_user_id, completed, trigger=SynchronizationTrigger.CONNECT,
    )
    if admission is ImmediateAdmission.BUSY:
        send(
            telegram_user_id,
            "Your login is saved. BookSaver is busy, so we haven't loaded your reservations. "
            "Please send /bookings again in a few minutes.",
        )
    elif admission is ImmediateAdmission.STOPPING:
        send(
            telegram_user_id,
            "Your login is saved, but BookSaver is shutting down. "
            "Please send /bookings once it is running again.",
        )
