from __future__ import annotations

from collections.abc import Callable
from datetime import date
from pathlib import Path

from booksaver.application.register_booking import register_booking
from booksaver.domain.errors import BookingRejectedError
from booksaver.domain.user import User
from booksaver.domain.value_objects import (
    ConfirmationId,
    LimitsSettings,
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
    SqliteUserRepository,
)

from .dialogs import DialogAborted, DialogDefinition, DialogManager, DialogStep
from .router import CommandRouter, IncomingCommand

Reply = Callable[[int, str], None]

_SKIP_TOKENS = {"-", "skip", "none", ""}


def _is_skip(text: str) -> bool:
    return text.strip().lower() in _SKIP_TOKENS


def _cap_message(limit: int) -> str:
    return (
        f"You already have {limit} active booking(s), the maximum this bot "
        "allows per user. Remove or archive one before registering another, "
        "or ask the owner to raise the limit."
    )


def register_booking_dialog(
    router: CommandRouter,
    dialog_manager: DialogManager,
    reply: Reply,
    db_path: Path,
    limits_settings: LimitsSettings,
) -> None:
    """Registers the `/register` guided dialog (US-025).

    Every answer is validated with the SAME domain value objects the CLI's
    `register` command uses (`Property`, `StayDates`, `RoomType`, `Money`,
    `ConfirmationId`, `Occupancy`) — no rules are duplicated here, only
    reformatted as chat prompts. On completion it calls the same shared
    `register_booking` application path as the CLI, scoped to the sender's
    resolved local user (`UserRepository.get_by_telegram_id`), so the booking
    a bot user registers is owned by them, not the daemon owner.

    The per-user active-booking cap (`limits.max_bookings_per_user`) is
    enforced twice: once at `/register` time (fail fast, don't even start the
    dialog) and again at save time (defends against a second registration
    racing to completion concurrently). The owner is exempt from the cap —
    they run the daemon and are trusted with unlimited bookings; invited
    users are not.
    """

    def _resolve_user(telegram_user_id: int) -> User | None:
        with SqliteStore(db_path) as store:
            return SqliteUserRepository(store).get_by_telegram_id(telegram_user_id)

    def _active_count(user_id: int) -> int:
        with SqliteStore(db_path) as store:
            return len(SqliteBookingRepository(store).list_active_for_user(user_id))

    def _validate_property_name(text: str, _answers: dict[str, str]) -> str | None:
        if not text.strip():
            return "Property name must be non-empty."
        return None

    def _validate_property_ref(text: str, _answers: dict[str, str]) -> str | None:
        if _is_skip(text):
            return None
        try:
            Property(name="placeholder", booking_com_ref=text.strip())
        except ValueError as e:
            return str(e)
        return None

    def _validate_check_in(text: str, _answers: dict[str, str]) -> str | None:
        try:
            date.fromisoformat(text.strip())
        except ValueError:
            return f"Invalid date '{text.strip()}'. Use YYYY-MM-DD, e.g. 2026-09-01."
        return None

    def _validate_check_out(text: str, answers: dict[str, str]) -> str | None:
        try:
            check_out = date.fromisoformat(text.strip())
        except ValueError:
            return f"Invalid date '{text.strip()}'. Use YYYY-MM-DD, e.g. 2026-09-01."
        check_in = date.fromisoformat(answers["check_in"])
        try:
            StayDates(check_in=check_in, check_out=check_out)
        except ValueError as e:
            return str(e)
        return None

    def _validate_room_type(text: str, _answers: dict[str, str]) -> str | None:
        try:
            RoomType(label=text.strip())
        except ValueError as e:
            return str(e)
        return None

    def _validate_baseline_price(text: str, _answers: dict[str, str]) -> str | None:
        parts = text.strip().split()
        if len(parts) != 2:
            return 'Enter as "amount CURRENCY", e.g. "250.00 EUR".'
        amount, currency = parts
        try:
            Money.of(amount, currency)
        except ValueError as e:
            return str(e)
        return None

    def _validate_refundable(text: str, _answers: dict[str, str]) -> str | None:
        normalized = text.strip().lower()
        if normalized in {"no", "n"}:
            # Same product constraint the CLI's registration service enforces
            # (BookingRejectedError("Only refundable bookings can be registered.")) —
            # here the user gets to answer honestly instead of the CLI's
            # hardcoded is_refundable=True, so this is the first path that can
            # actually reach it.
            raise DialogAborted(
                "Registration rejected: Only refundable bookings can be registered.\n"
                "BookSaver only tracks refundable Booking.com reservations — nothing was saved."
            )
        if normalized not in {"yes", "y"}:
            return "Please reply yes or no — is this booking refundable?"
        return None

    def _validate_refund_note(_text: str, _answers: dict[str, str]) -> str | None:
        return None

    def _validate_refund_deadline(text: str, _answers: dict[str, str]) -> str | None:
        if _is_skip(text):
            return None
        try:
            date.fromisoformat(text.strip())
        except ValueError:
            return f"Invalid date '{text.strip()}'. Use YYYY-MM-DD, or '-' to skip."
        return None

    def _validate_adults(text: str, _answers: dict[str, str]) -> str | None:
        try:
            adults = int(text.strip())
        except ValueError:
            return "Enter a whole number of adults (at least 1)."
        try:
            Occupancy(adults=adults)
        except ValueError as e:
            return str(e)
        return None

    def _validate_children(text: str, answers: dict[str, str]) -> str | None:
        if _is_skip(text):
            return None
        try:
            children = int(text.strip())
        except ValueError:
            return "Enter a whole number of children (0 or more), or '-' for none."
        try:
            Occupancy(adults=int(answers["occ_adults"]), children=children)
        except ValueError as e:
            return str(e)
        return None

    def _validate_rooms(text: str, answers: dict[str, str]) -> str | None:
        if _is_skip(text):
            return None
        try:
            rooms = int(text.strip())
        except ValueError:
            return "Enter a whole number of rooms (at least 1), or '-' for 1."
        children_answer = answers.get("occ_children", "-")
        children = 0 if _is_skip(children_answer) else int(children_answer)
        try:
            Occupancy(adults=int(answers["occ_adults"]), children=children, rooms=rooms)
        except ValueError as e:
            return str(e)
        return None

    def _validate_confirmation_id(text: str, _answers: dict[str, str]) -> str | None:
        try:
            ConfirmationId.of(text)
        except ValueError as e:
            return str(e)
        return None

    def _summary_prompt(answers: dict[str, str]) -> str:
        ref = (
            answers["property_name"]
            if _is_skip(answers["property_ref"])
            else answers["property_ref"]
        )
        note = "" if _is_skip(answers["refund_note"]) else answers["refund_note"]
        deadline = "" if _is_skip(answers["refund_deadline"]) else answers["refund_deadline"]
        children = "0" if _is_skip(answers.get("occ_children", "-")) else answers["occ_children"]
        rooms = "1" if _is_skip(answers.get("occ_rooms", "-")) else answers["occ_rooms"]
        refundable_line = "yes"
        if note:
            refundable_line += f" ({note})"
        if deadline:
            refundable_line += f", deadline {deadline}"
        lines = [
            "Please confirm this booking:",
            f"Property     : {answers['property_name']} ({ref})",
            f"Stay         : {answers['check_in']} -> {answers['check_out']}",
            f"Room         : {answers['room_type']}",
            f"Baseline     : {answers['baseline_price']}",
            f"Refundable   : {refundable_line}",
            f"Occupancy    : {answers['occ_adults']} adult(s), "
            f"{children} child(ren), {rooms} room(s)",
            f"Confirmation : {answers['confirmation_id']}",
            "",
            "Reply yes to save, or no to cancel.",
        ]
        return "\n".join(lines)

    def _validate_confirm(text: str, _answers: dict[str, str]) -> str | None:
        normalized = text.strip().lower()
        if normalized in {"no", "n"}:
            raise DialogAborted("Registration cancelled. Nothing was saved.")
        if normalized not in {"yes", "y"}:
            return "Reply yes to save, or no to cancel."
        return None

    def _on_complete(user_id: int, chat_id: int, answers: dict[str, str]) -> str:
        with SqliteStore(db_path) as store:
            booking_repo = SqliteBookingRepository(store)
            user_repo = SqliteUserRepository(store)
            user = user_repo.get_by_telegram_id(user_id)
            if user is None or not user.is_active:
                return "You're not recognized by this bot anymore — registration cancelled."
            if (
                not user.is_owner
                and len(booking_repo.list_active_for_user(user.user_id))
                >= limits_settings.max_bookings_per_user
            ):
                return _cap_message(limits_settings.max_bookings_per_user)

            ref = (
                answers["property_name"]
                if _is_skip(answers["property_ref"])
                else answers["property_ref"]
            )
            amount, currency = answers["baseline_price"].strip().split()
            note = "" if _is_skip(answers["refund_note"]) else answers["refund_note"].strip()
            deadline_str = answers["refund_deadline"]
            deadline = None if _is_skip(deadline_str) else date.fromisoformat(deadline_str.strip())
            children_answer = answers.get("occ_children", "-")
            children = 0 if _is_skip(children_answer) else int(children_answer)
            rooms_answer = answers.get("occ_rooms", "-")
            rooms = 1 if _is_skip(rooms_answer) else int(rooms_answer)

            try:
                booking, _event = register_booking(
                    repo=booking_repo,
                    platform=Platform.BOOKING_COM,
                    product_type=ProductType.HOTEL,
                    confirmation_id=ConfirmationId.of(answers["confirmation_id"]),
                    property=Property(
                        name=answers["property_name"].strip(), booking_com_ref=ref.strip()
                    ),
                    stay_dates=StayDates(
                        check_in=date.fromisoformat(answers["check_in"]),
                        check_out=date.fromisoformat(answers["check_out"]),
                    ),
                    room_type=RoomType(label=answers["room_type"].strip()),
                    baseline_price=Money.of(amount, currency),
                    refundability=RefundabilityPolicy(
                        is_refundable=True, note=note, deadline=deadline
                    ),
                    occupancy=Occupancy(
                        adults=int(answers["occ_adults"]), children=children, rooms=rooms
                    ),
                    user_id=user.user_id,
                )
            except BookingRejectedError as e:
                return f"Registration rejected: {e}"

        return (
            f"Registered: {booking.booking_id}\n"
            f"  Confirmation : {booking.confirmation_id.value}\n"
            f"  Property     : {booking.property.name}\n"
            f"  Stay         : {booking.stay_dates.check_in} -> {booking.stay_dates.check_out}\n"
            f"  Room         : {booking.room_type.label}\n"
            f"  Baseline     : {booking.baseline_price.amount} {booking.baseline_price.currency}\n"
            f"  Occupancy    : {booking.occupancy}"
        )

    definition = DialogDefinition(
        name="register",
        steps=(
            DialogStep(
                key="property_name",
                prompt="Let's register a booking. What's the property name?",
                validate=_validate_property_name,
            ),
            DialogStep(
                key="property_ref",
                prompt="Booking.com property URL or reference? Reply '-' to skip.",
                validate=_validate_property_ref,
            ),
            DialogStep(
                key="check_in",
                prompt="Check-in date? (YYYY-MM-DD)",
                validate=_validate_check_in,
            ),
            DialogStep(
                key="check_out",
                prompt="Check-out date? (YYYY-MM-DD)",
                validate=_validate_check_out,
            ),
            DialogStep(
                key="room_type",
                prompt='Room type? (e.g. "Standard Double")',
                validate=_validate_room_type,
            ),
            DialogStep(
                key="baseline_price",
                prompt='Baseline all-in price you paid, as "amount CURRENCY" (e.g. "250.00 EUR").',
                validate=_validate_baseline_price,
            ),
            DialogStep(
                key="refundable",
                prompt=(
                    "Is this booking refundable? BookSaver only tracks refundable "
                    "bookings. Reply yes or no."
                ),
                validate=_validate_refundable,
            ),
            DialogStep(
                key="refund_note",
                prompt=(
                    "Any note about the refund policy (e.g. 'Free cancellation until "
                    "Sep 1')? Reply '-' for none."
                ),
                validate=_validate_refund_note,
            ),
            DialogStep(
                key="refund_deadline",
                prompt="Refund deadline date? (YYYY-MM-DD, or '-' to skip)",
                validate=_validate_refund_deadline,
            ),
            DialogStep(
                key="occ_adults",
                prompt="How many adults is this booking for?",
                validate=_validate_adults,
            ),
            DialogStep(
                key="occ_children",
                prompt="How many children? Reply '-' for 0.",
                validate=_validate_children,
            ),
            DialogStep(
                key="occ_rooms",
                prompt="How many rooms? Reply '-' for 1.",
                validate=_validate_rooms,
            ),
            DialogStep(
                key="confirmation_id",
                prompt="Booking.com confirmation ID?",
                validate=_validate_confirmation_id,
            ),
            DialogStep(key="confirm", prompt=_summary_prompt, validate=_validate_confirm),
        ),
        on_complete=_on_complete,
    )

    def _start_register(cmd: IncomingCommand) -> None:
        user = _resolve_user(cmd.user_id)
        if user is None or not user.is_active:
            reply(cmd.chat_id, "You're not recognized by this bot yet.")
            return
        at_cap = _active_count(user.user_id) >= limits_settings.max_bookings_per_user
        if not user.is_owner and at_cap:
            reply(cmd.chat_id, _cap_message(limits_settings.max_bookings_per_user))
            return
        prompt = dialog_manager.start(cmd.chat_id, definition)
        reply(cmd.chat_id, prompt)

    router.register("/register", _start_register)
