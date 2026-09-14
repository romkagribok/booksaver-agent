"""Plain-language guidance for reservation refresh failures."""

from booksaver.domain.account_sync import SynchronizationFailureCode


def refresh_failure_guidance(code: SynchronizationFailureCode | None) -> str:
    if code is SynchronizationFailureCode.AUTH_REQUIRED:
        return "Booking.com needs you to sign in again. Send /connect to reconnect."
    if code is SynchronizationFailureCode.USER_KEY_INVALID:
        return (
            "Your personal AI key isn't working. Send /setkey to replace it, "
            "or /deletekey to use the bot's shared key."
        )
    return "Try /bookings again in a few minutes."


def empty_upcoming_message(*, has_saved: bool) -> str:
    message = "We did not find upcoming hotel reservations in the trips we checked. "
    if has_saved:
        return message + "Your previously saved reservations are still here."
    return message + "If you expected a booking, check which Booking.com account you signed in to."
