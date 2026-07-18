from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path
from typing import Any

from booksaver.daemon.check_coordinator import (
    CheckCoordinator,
    ImmediateAdmission,
    ImmediateCompletion,
    ImmediateCompletionKind,
)
from booksaver.domain.check_result import CheckOutcome
from booksaver.domain.models import Booking
from booksaver.infrastructure.persistence.sqlite_store import (
    SqliteBookingRepository,
    SqliteStore,
    SqliteUserRepository,
)

from .client import TelegramBotClient
from .router import CallbackRouter, CommandRouter, IncomingCallback, IncomingCommand

logger = logging.getLogger(__name__)

Reply = Callable[[int, str], None]
Send = Callable[[int, str, dict[str, Any] | None], None]

_UNAVAILABLE = "That booking is not available. Choose one of your active bookings."


def register_check_now_command(
    *,
    router: CommandRouter,
    callback_router: CallbackRouter,
    reply: Reply,
    send: Send,
    client: TelegramBotClient,
    db_path: Path,
    coordinator: CheckCoordinator | None,
) -> None:
    """Register caller-scoped `/checknow` selection and background reporting."""

    def _owned_active(telegram_user_id: int) -> list[Booking]:
        if not db_path.exists():
            return []
        with SqliteStore(db_path) as store:
            user = SqliteUserRepository(store).get_by_telegram_id(telegram_user_id)
            if user is None or not user.is_active:
                return []
            return SqliteBookingRepository(store).list_active_for_user(user.user_id)

    def _resolve(telegram_user_id: int, selector: str) -> Booking | None:
        bookings = _owned_active(telegram_user_id)
        exact = [booking for booking in bookings if booking.booking_id == selector]
        if len(exact) == 1:
            return exact[0]
        if len(selector) < 8:
            return None
        matches = [booking for booking in bookings if booking.booking_id.startswith(selector)]
        return matches[0] if len(matches) == 1 else None

    def _format_completion(completion: ImmediateCompletion) -> str:
        if completion.kind is ImmediateCompletionKind.UNAVAILABLE:
            return _UNAVAILABLE
        result = completion.result
        if result is None:
            return "The live check could not be completed. Please try again later."
        prefix = result.check_id[:8]
        property_name = completion.property_name or "booking"
        if result.outcome is CheckOutcome.SUCCESS and result.live_price is not None:
            return (
                f"Live check complete for {property_name}: "
                f"{result.live_price.amount} {result.live_price.currency} "
                f"(check {prefix})."
            )
        reason = result.failure_reason
        if reason is None:
            return f"Live check failed for {property_name} (check {prefix})."
        detail = " ".join(reason.detail.split())[:180]
        return (
            f"Live check failed for {property_name}: {reason.code.value} — "
            f"{detail} (check {prefix})."
        )

    def _request(telegram_user_id: int, chat_id: int, booking: Booking) -> str:
        if coordinator is None:
            return "Immediate checks are unavailable until the daemon is restarted."

        def _complete(completion: ImmediateCompletion) -> None:
            send(chat_id, _format_completion(completion), None)

        admission = coordinator.request_immediate(
            telegram_user_id, booking.booking_id, _complete
        )
        if admission is ImmediateAdmission.BUSY:
            return "A live check is already running. Try again after it finishes."
        if admission is ImmediateAdmission.STOPPING:
            return "BookSaver is shutting down; no new check was started."
        return f"Checking {booking.property.name} now. I'll send the result here."

    def _command(cmd: IncomingCommand) -> None:
        selector = cmd.args.strip()
        if selector:
            booking = _resolve(cmd.user_id, selector)
            reply(cmd.chat_id, _UNAVAILABLE if booking is None else _request(
                cmd.user_id, cmd.chat_id, booking
            ))
            return
        bookings = _owned_active(cmd.user_id)
        if not bookings:
            reply(cmd.chat_id, "No active bookings to check.")
            return
        keyboard = {
            "inline_keyboard": [
                [
                    {
                        "text": (
                            f"{booking.property.name[:35]} · "
                            f"{booking.stay_dates.check_in:%b %d}–"
                            f"{booking.stay_dates.check_out:%b %d}"
                        ),
                        "callback_data": f"checknow:{booking.booking_id}",
                    }
                ]
                for booking in bookings[:10]
            ]
        }
        send(cmd.chat_id, "Choose a booking to check now:", keyboard)

    def _callback(callback: IncomingCallback) -> None:
        selector = callback.data.removeprefix("checknow:")
        booking = _resolve(callback.user_id, selector)
        text = _UNAVAILABLE if booking is None else _request(
            callback.user_id, callback.chat_id, booking
        )
        try:
            client.answer_callback_query(callback.callback_query_id)
        except Exception:
            logger.warning("Could not answer check-now callback")
        try:
            client.edit_message_text(callback.chat_id, callback.message_id, text)
        except Exception:
            logger.warning("Could not edit check-now selection message")

    router.register("/checknow", _command)
    callback_router.register("checknow:", _callback)
