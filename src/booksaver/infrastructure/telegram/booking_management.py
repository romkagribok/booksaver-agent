from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from datetime import date
from pathlib import Path
from typing import Any

from booksaver.application.manage_booking import delete_booking, update_booking
from booksaver.domain.errors import BookingRejectedError
from booksaver.domain.models import Booking
from booksaver.domain.value_objects import (
    ConfirmationId,
    Money,
    Occupancy,
    Property,
    RefundabilityPolicy,
    RoomType,
    StayDates,
)
from booksaver.infrastructure.persistence.sqlite_store import (
    SqliteBookingRepository,
    SqliteStore,
    SqliteUserRepository,
)

from .client import TelegramBotClient
from .dialogs import DialogDefinition, DialogManager, DialogStep
from .router import CallbackRouter, CommandRouter, IncomingCallback, IncomingCommand

Reply = Callable[[int, str], None]
Send = Callable[[int, str, dict[str, Any] | None], None]

_NOT_FOUND = "Booking not found."
_EDIT_FIELDS = (
    ("property", "Property / Booking.com reference"),
    ("dates", "Stay dates"),
    ("room", "Room type"),
    ("price", "Baseline price"),
    ("refund", "Refund policy details"),
    ("occupancy", "Guests / rooms"),
    ("confirmation", "Confirmation ID"),
)


def _booking_label(booking: Booking) -> str:
    return (
        f"{booking.property.name[:35]} · "
        f"{booking.stay_dates.check_in:%b %d}–{booking.stay_dates.check_out:%b %d}"
    )


def register_booking_management_commands(
    router: CommandRouter,
    callback_router: CallbackRouter,
    dialog_manager: DialogManager,
    reply: Reply,
    send: Send,
    client: TelegramBotClient,
    db_path: Path,
) -> None:
    """Register caller-scoped `/editbooking` and `/deletebooking` flows."""

    def _owned_bookings(telegram_user_id: int) -> list[Booking] | None:
        if not db_path.exists():
            return []
        with SqliteStore(db_path) as store:
            user = SqliteUserRepository(store).get_by_telegram_id(telegram_user_id)
            if user is None or not user.is_active:
                return None
            return SqliteBookingRepository(store).list_active_for_user(user.user_id)

    def _resolve_owned(telegram_user_id: int, selector: str) -> Booking | None:
        bookings = _owned_bookings(telegram_user_id)
        if bookings is None:
            return None
        exact = next((item for item in bookings if item.booking_id == selector), None)
        if exact is not None:
            return exact
        if len(selector) < 8:
            return None
        matches = [item for item in bookings if item.booking_id.startswith(selector)]
        return matches[0] if len(matches) == 1 else None

    def _booking_keyboard(prefix: str, bookings: list[Booking]) -> dict[str, Any]:
        return {
            "inline_keyboard": [
                [
                    {
                        "text": _booking_label(booking),
                        "callback_data": f"{prefix}:{booking.booking_id}",
                    }
                ]
                for booking in bookings[:10]
            ]
        }

    def _edit_field_keyboard(booking_id: str) -> dict[str, Any]:
        rows = [
            [
                {
                    "text": label,
                    "callback_data": f"bedit:{booking_id}:{key}",
                }
            ]
            for key, label in _EDIT_FIELDS
        ]
        rows.append([{"text": "← Back", "callback_data": "bedit:list"}])
        return {"inline_keyboard": rows}

    def _delete_keyboard(booking_id: str) -> dict[str, Any]:
        return {
            "inline_keyboard": [
                [
                    {
                        "text": "Delete permanently",
                        "callback_data": f"bdel:{booking_id}:confirm",
                    },
                    {"text": "Cancel", "callback_data": f"bdel:{booking_id}:cancel"},
                ],
                [{"text": "← Back", "callback_data": "bdel:list"}],
            ]
        }

    def _show_edit_picker(chat_id: int, telegram_user_id: int) -> None:
        bookings = _owned_bookings(telegram_user_id)
        if bookings is None:
            reply(chat_id, "You're not recognized by this bot.")
        elif not bookings:
            reply(chat_id, "No active bookings to edit.")
        else:
            send(chat_id, "Choose a booking to edit:", _booking_keyboard("bedit", bookings))

    def _show_delete_picker(chat_id: int, telegram_user_id: int) -> None:
        bookings = _owned_bookings(telegram_user_id)
        if bookings is None:
            reply(chat_id, "You're not recognized by this bot.")
        elif not bookings:
            reply(chat_id, "No active bookings to delete.")
        else:
            send(
                chat_id,
                "Choose a booking to delete:",
                _booking_keyboard("bdel", bookings),
            )

    def _edit_picker_text(booking: Booking) -> str:
        return (
            f"Editing {booking.property.name}\n"
            f"{booking.stay_dates.check_in} → {booking.stay_dates.check_out}\n\n"
            "Choose what to change:"
        )

    def _delete_prompt(booking: Booking) -> str:
        return (
            f"Delete {booking.property.name} "
            f"({booking.stay_dates.check_in} → {booking.stay_dates.check_out})?\n\n"
            "This permanently removes the local booking plus its check history, traces, savings, "
            "and rebook history. It does not cancel anything on Booking.com."
        )

    def _validate_nonempty(label: str) -> Callable[[str, dict[str, str]], str | None]:
        def _validate(text: str, _answers: dict[str, str]) -> str | None:
            return None if text.strip() else f"{label} must be non-empty."

        return _validate

    def _validate_date(text: str, _answers: dict[str, str]) -> str | None:
        try:
            date.fromisoformat(text.strip())
        except ValueError:
            return f"Invalid date '{text.strip()}'. Use YYYY-MM-DD."
        return None

    def _validate_check_out(text: str, answers: dict[str, str]) -> str | None:
        error = _validate_date(text, answers)
        if error is not None:
            return error
        try:
            StayDates(
                check_in=date.fromisoformat(answers["check_in"].strip()),
                check_out=date.fromisoformat(text.strip()),
            )
        except ValueError as exc:
            return str(exc)
        return None

    def _validate_money(text: str, _answers: dict[str, str]) -> str | None:
        parts = text.strip().split()
        if len(parts) != 2:
            return 'Enter as "amount CURRENCY", e.g. "250.00 EUR".'
        try:
            Money.of(parts[0], parts[1])
        except ValueError as exc:
            return str(exc)
        return None

    def _validate_optional_date(text: str, answers: dict[str, str]) -> str | None:
        if text.strip() == "-":
            return None
        return _validate_date(text, answers)

    def _validate_int(minimum: int, label: str) -> Callable[[str, dict[str, str]], str | None]:
        def _validate(text: str, _answers: dict[str, str]) -> str | None:
            try:
                value = int(text.strip())
            except ValueError:
                return f"{label} must be a whole number."
            if value < minimum:
                return f"{label} must be at least {minimum}."
            return None

        return _validate

    def _validate_ref(text: str, _answers: dict[str, str]) -> str | None:
        if text.strip() == "-":
            return None
        try:
            Property(name="placeholder", booking_com_ref=text.strip())
        except ValueError as exc:
            return str(exc)
        return None

    def _build_dialog(booking: Booking, field: str) -> DialogDefinition:
        prompts: dict[str, tuple[DialogStep, ...]] = {
            "property": (
                DialogStep(
                    "property_name",
                    f"New property name? Current: {booking.property.name}",
                    _validate_nonempty("Property name"),
                ),
                DialogStep(
                    "property_ref",
                    "New Booking.com URL/reference? Reply '-' to keep the current reference.",
                    _validate_ref,
                ),
            ),
            "dates": (
                DialogStep(
                    "check_in",
                    f"New check-in date? (YYYY-MM-DD; current {booking.stay_dates.check_in})",
                    _validate_date,
                ),
                DialogStep(
                    "check_out",
                    f"New check-out date? (YYYY-MM-DD; current {booking.stay_dates.check_out})",
                    _validate_check_out,
                ),
            ),
            "room": (
                DialogStep(
                    "room_type",
                    f"New room type? Current: {booking.room_type.label}",
                    _validate_nonempty("Room type"),
                ),
            ),
            "price": (
                DialogStep(
                    "baseline_price",
                    "New all-in baseline as 'amount CURRENCY' "
                    f"(current {booking.baseline_price.amount} {booking.baseline_price.currency})?",
                    _validate_money,
                ),
            ),
            "refund": (
                DialogStep(
                    "refund_note",
                    f"New refund-policy note? Current: {booking.refundability.note or '(none)'}. "
                    "Reply '-' to clear it.",
                    lambda _text, _answers: None,
                ),
                DialogStep(
                    "refund_deadline",
                    "New refund deadline? (YYYY-MM-DD, or '-' to clear it)",
                    _validate_optional_date,
                ),
            ),
            "occupancy": (
                DialogStep(
                    "adults",
                    "Adults? Current: "
                    f"{booking.occupancy.adults if booking.occupancy else 'unknown'}",
                    _validate_int(1, "Adults"),
                ),
                DialogStep(
                    "children",
                    f"Children? Current: {booking.occupancy.children if booking.occupancy else 0}",
                    _validate_int(0, "Children"),
                ),
                DialogStep(
                    "rooms",
                    f"Rooms? Current: {booking.occupancy.rooms if booking.occupancy else 1}",
                    _validate_int(1, "Rooms"),
                ),
            ),
            "confirmation": (
                DialogStep(
                    "confirmation_id",
                    f"New Booking.com confirmation ID? Current: {booking.confirmation_id.value}",
                    _validate_nonempty("Confirmation ID"),
                ),
            ),
        }

        def _complete(telegram_user_id: int, _chat_id: int, answers: dict[str, str]) -> str:
            current = _resolve_owned(telegram_user_id, booking.booking_id)
            if current is None:
                return _NOT_FOUND
            try:
                if field == "property":
                    ref = answers["property_ref"].strip()
                    updated = replace(
                        current,
                        property=Property(
                            name=answers["property_name"].strip(),
                            booking_com_ref=(
                                current.property.booking_com_ref if ref == "-" else ref
                            ),
                        ),
                    )
                elif field == "dates":
                    updated = replace(
                        current,
                        stay_dates=StayDates(
                            date.fromisoformat(answers["check_in"].strip()),
                            date.fromisoformat(answers["check_out"].strip()),
                        ),
                    )
                elif field == "room":
                    updated = replace(
                        current, room_type=RoomType(answers["room_type"].strip())
                    )
                elif field == "price":
                    amount, currency = answers["baseline_price"].strip().split()
                    updated = replace(current, baseline_price=Money.of(amount, currency))
                elif field == "refund":
                    note = answers["refund_note"].strip()
                    deadline = answers["refund_deadline"].strip()
                    updated = replace(
                        current,
                        refundability=RefundabilityPolicy(
                            is_refundable=True,
                            note="" if note == "-" else note,
                            deadline=None if deadline == "-" else date.fromisoformat(deadline),
                        ),
                    )
                elif field == "occupancy":
                    updated = replace(
                        current,
                        occupancy=Occupancy(
                            adults=int(answers["adults"]),
                            children=int(answers["children"]),
                            rooms=int(answers["rooms"]),
                        ),
                    )
                else:
                    updated = replace(
                        current,
                        confirmation_id=ConfirmationId.of(answers["confirmation_id"]),
                    )
                with SqliteStore(db_path) as store:
                    update_booking(SqliteBookingRepository(store), updated)
            except (BookingRejectedError, ValueError) as exc:
                return f"Booking was not updated: {exc}"
            except KeyError:
                return _NOT_FOUND
            return f"Updated {updated.property.name}. Future checks will use the new details."

        return DialogDefinition(
            name=f"editbooking:{booking.booking_id}:{field}",
            steps=prompts[field],
            on_complete=_complete,
        )

    def _edit_command(cmd: IncomingCommand) -> None:
        dialog_manager.cancel(cmd.chat_id)
        selector = cmd.args.strip()
        if not selector:
            _show_edit_picker(cmd.chat_id, cmd.user_id)
            return
        booking = _resolve_owned(cmd.user_id, selector)
        if booking is None:
            reply(cmd.chat_id, _NOT_FOUND)
            return
        send(cmd.chat_id, _edit_picker_text(booking), _edit_field_keyboard(booking.booking_id))

    def _delete_command(cmd: IncomingCommand) -> None:
        dialog_manager.cancel(cmd.chat_id)
        selector = cmd.args.strip()
        if not selector:
            _show_delete_picker(cmd.chat_id, cmd.user_id)
            return
        booking = _resolve_owned(cmd.user_id, selector)
        if booking is None:
            reply(cmd.chat_id, _NOT_FOUND)
            return
        send(cmd.chat_id, _delete_prompt(booking), _delete_keyboard(booking.booking_id))

    def _edit_callback(callback: IncomingCallback) -> None:
        client.answer_callback_query(callback.callback_query_id)
        parts = callback.data.split(":")
        if parts == ["bedit", "list"]:
            bookings = _owned_bookings(callback.user_id)
            if not bookings:
                client.edit_message_text(
                    callback.chat_id, callback.message_id, "No active bookings to edit."
                )
                return
            client.edit_message_text(
                callback.chat_id,
                callback.message_id,
                "Choose a booking to edit:",
                _booking_keyboard("bedit", bookings),
            )
            return
        if len(parts) not in {2, 3}:
            client.edit_message_text(callback.chat_id, callback.message_id, _NOT_FOUND)
            return
        booking = _resolve_owned(callback.user_id, parts[1])
        if booking is None:
            client.edit_message_text(callback.chat_id, callback.message_id, _NOT_FOUND)
            return
        if len(parts) == 2:
            dialog_manager.cancel(callback.chat_id)
            client.edit_message_text(
                callback.chat_id,
                callback.message_id,
                _edit_picker_text(booking),
                _edit_field_keyboard(booking.booking_id),
            )
            return
        field = parts[2]
        if field not in {key for key, _label in _EDIT_FIELDS}:
            client.edit_message_text(callback.chat_id, callback.message_id, _NOT_FOUND)
            return
        prompt = dialog_manager.start(callback.chat_id, _build_dialog(booking, field))
        client.edit_message_text(callback.chat_id, callback.message_id, prompt)

    def _delete_callback(callback: IncomingCallback) -> None:
        client.answer_callback_query(callback.callback_query_id)
        parts = callback.data.split(":")
        if parts == ["bdel", "list"]:
            bookings = _owned_bookings(callback.user_id)
            if not bookings:
                client.edit_message_text(
                    callback.chat_id, callback.message_id, "No active bookings to delete."
                )
                return
            client.edit_message_text(
                callback.chat_id,
                callback.message_id,
                "Choose a booking to delete:",
                _booking_keyboard("bdel", bookings),
            )
            return
        if len(parts) not in {2, 3}:
            client.edit_message_text(callback.chat_id, callback.message_id, _NOT_FOUND)
            return
        booking = _resolve_owned(callback.user_id, parts[1])
        if booking is None:
            client.edit_message_text(callback.chat_id, callback.message_id, _NOT_FOUND)
            return
        if len(parts) == 2:
            dialog_manager.cancel(callback.chat_id)
            client.edit_message_text(
                callback.chat_id,
                callback.message_id,
                _delete_prompt(booking),
                _delete_keyboard(booking.booking_id),
            )
            return
        action = parts[2]
        if action == "cancel":
            dialog_manager.cancel(callback.chat_id)
            client.edit_message_text(
                callback.chat_id,
                callback.message_id,
                "Deletion cancelled. Nothing was deleted.",
            )
            return
        if action != "confirm":
            client.edit_message_text(callback.chat_id, callback.message_id, _NOT_FOUND)
            return
        dialog_manager.cancel(callback.chat_id)
        try:
            with SqliteStore(db_path) as store:
                deleted = delete_booking(SqliteBookingRepository(store), booking.booking_id)
        except BookingRejectedError as exc:
            client.edit_message_text(
                callback.chat_id,
                callback.message_id,
                f"Booking was not deleted: {exc}",
            )
            return
        client.edit_message_text(
            callback.chat_id,
            callback.message_id,
            f"Deleted {booking.property.name}." if deleted else _NOT_FOUND,
        )

    router.register("/editbooking", _edit_command)
    router.register("/deletebooking", _delete_command)
    callback_router.register("bedit:", _edit_callback)
    callback_router.register("bdel:", _delete_callback)
