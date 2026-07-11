from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

from booksaver.domain.user import UserRole
from booksaver.domain.value_objects import LimitsSettings
from booksaver.infrastructure.persistence.sqlite_store import (
    SqliteBookingRepository,
    SqliteStore,
    SqliteUserRepository,
)
from booksaver.infrastructure.telegram.dialogs import DialogManager
from booksaver.infrastructure.telegram.register_dialog import register_booking_dialog
from booksaver.infrastructure.telegram.router import CommandRouter, IncomingCommand


def _setup(tmp_path: Path, max_bookings_per_user: int = 3):
    db_path = tmp_path / "booksaver.db"
    router = CommandRouter()
    dialog_manager = DialogManager()
    sent: list[tuple[int, str]] = []
    limits = LimitsSettings(max_bookings_per_user=max_bookings_per_user)
    register_booking_dialog(
        router=router,
        dialog_manager=dialog_manager,
        reply=lambda chat_id, text: sent.append((chat_id, text)),
        db_path=db_path,
        limits_settings=limits,
    )
    return db_path, router, dialog_manager, sent


def _register_user(db_path: Path, telegram_id: int, role: UserRole = UserRole.USER) -> int:
    with SqliteStore(db_path) as store:
        user = SqliteUserRepository(store).get_or_create_by_telegram_id(telegram_id, role=role)
        return user.user_id


def _send_command(router: CommandRouter, chat_id: int, user_id: int, command: str) -> None:
    router.dispatch(
        IncomingCommand(
            user_id=user_id, chat_id=chat_id, command=command, args="", raw_text=command
        )
    )


def _send_text(
    dialog_manager: DialogManager, sent: list, chat_id: int, user_id: int, text: str
) -> str:
    reply = dialog_manager.handle_message(chat_id, user_id, text)
    sent.append((chat_id, reply))
    return reply


_HAPPY_PATH_ANSWERS = [
    "Ibis Berlin Mitte",  # property_name
    "-",  # property_ref (skip)
    "2026-09-01",  # check_in
    "2026-09-05",  # check_out
    "Standard Double",  # room_type
    "250.00 EUR",  # baseline_price
    "yes",  # refundable
    "-",  # refund_note (skip)
    "-",  # refund_deadline (skip)
    "2",  # occ_adults
    "-",  # occ_children
    "-",  # occ_rooms
    "CONF123",  # confirmation_id
]


def _drive_to_confirm(
    dialog_manager: DialogManager, sent: list, chat_id: int, user_id: int
) -> None:
    for answer in _HAPPY_PATH_ANSWERS:
        _send_text(dialog_manager, sent, chat_id, user_id, answer)


def test_full_happy_path_registers_the_same_booking_aggregate_as_cli(tmp_path: Path) -> None:
    db_path, router, dialog_manager, sent = _setup(tmp_path)
    telegram_id = 111
    user_id = _register_user(db_path, telegram_id)

    _send_command(router, telegram_id, telegram_id, "/register")
    assert dialog_manager.has_active(telegram_id) is True

    _drive_to_confirm(dialog_manager, sent, telegram_id, telegram_id)
    final_reply = _send_text(dialog_manager, sent, telegram_id, telegram_id, "yes")

    assert "Registered:" in final_reply
    assert dialog_manager.has_active(telegram_id) is False

    with SqliteStore(db_path) as store:
        bookings = SqliteBookingRepository(store).list_active_for_user(user_id)
    assert len(bookings) == 1
    booking = bookings[0]
    assert booking.property.name == "Ibis Berlin Mitte"
    # ref skipped -> falls back to the property name
    assert booking.property.booking_com_ref == "Ibis Berlin Mitte"
    assert booking.stay_dates.check_in == date(2026, 9, 1)
    assert booking.stay_dates.check_out == date(2026, 9, 5)
    assert booking.room_type.label == "Standard Double"
    assert booking.baseline_price.amount == Decimal("250.00")
    assert booking.baseline_price.currency == "EUR"
    assert booking.refundability.is_refundable is True
    assert booking.refundability.note == ""
    assert booking.refundability.deadline is None
    assert booking.occupancy is not None
    assert booking.occupancy.adults == 2
    assert booking.occupancy.children == 0
    assert booking.occupancy.rooms == 1
    assert booking.confirmation_id.value == "CONF123"


def test_summary_step_shows_full_recap_before_confirming(tmp_path: Path) -> None:
    db_path, router, dialog_manager, sent = _setup(tmp_path)
    telegram_id = 111
    _register_user(db_path, telegram_id)

    _send_command(router, telegram_id, telegram_id, "/register")
    for answer in _HAPPY_PATH_ANSWERS[:-1]:
        _send_text(dialog_manager, sent, telegram_id, telegram_id, answer)
    summary_reply = _send_text(
        dialog_manager, sent, telegram_id, telegram_id, _HAPPY_PATH_ANSWERS[-1]
    )

    assert "Please confirm this booking" in summary_reply
    assert "Ibis Berlin Mitte" in summary_reply
    assert "CONF123" in summary_reply
    assert "Reply yes to save, or no to cancel." in summary_reply


def test_confirm_no_aborts_without_saving(tmp_path: Path) -> None:
    db_path, router, dialog_manager, sent = _setup(tmp_path)
    telegram_id = 111
    user_id = _register_user(db_path, telegram_id)

    _send_command(router, telegram_id, telegram_id, "/register")
    _drive_to_confirm(dialog_manager, sent, telegram_id, telegram_id)
    final_reply = _send_text(dialog_manager, sent, telegram_id, telegram_id, "no")

    assert final_reply == "Registration cancelled. Nothing was saved."
    assert dialog_manager.has_active(telegram_id) is False

    with SqliteStore(db_path) as store:
        bookings = SqliteBookingRepository(store).list_active_for_user(user_id)
    assert bookings == []


def test_non_refundable_answer_aborts_with_cli_identical_message(tmp_path: Path) -> None:
    db_path, router, dialog_manager, sent = _setup(tmp_path)
    telegram_id = 111
    _register_user(db_path, telegram_id)

    _send_command(router, telegram_id, telegram_id, "/register")
    for answer in _HAPPY_PATH_ANSWERS[:6]:  # up to and including baseline_price
        _send_text(dialog_manager, sent, telegram_id, telegram_id, answer)
    reply = _send_text(dialog_manager, sent, telegram_id, telegram_id, "no")

    assert "Only refundable bookings can be registered." in reply
    assert dialog_manager.has_active(telegram_id) is False


def test_invalid_date_order_reprompts_with_domain_message(tmp_path: Path) -> None:
    db_path, router, dialog_manager, sent = _setup(tmp_path)
    telegram_id = 111
    _register_user(db_path, telegram_id)

    _send_command(router, telegram_id, telegram_id, "/register")
    _send_text(dialog_manager, sent, telegram_id, telegram_id, "Ibis Berlin")
    _send_text(dialog_manager, sent, telegram_id, telegram_id, "-")
    _send_text(dialog_manager, sent, telegram_id, telegram_id, "2026-09-05")
    reply = _send_text(dialog_manager, sent, telegram_id, telegram_id, "2026-09-01")

    assert "must be after check_in" in reply
    assert "Check-out date?" in reply
    assert dialog_manager.has_active(telegram_id) is True  # still on check_out step


def test_bad_occupancy_reprompts_with_domain_message(tmp_path: Path) -> None:
    db_path, router, dialog_manager, sent = _setup(tmp_path)
    telegram_id = 111
    _register_user(db_path, telegram_id)

    _send_command(router, telegram_id, telegram_id, "/register")
    for answer in _HAPPY_PATH_ANSWERS[:9]:  # up to and including refund_deadline
        _send_text(dialog_manager, sent, telegram_id, telegram_id, answer)
    reply = _send_text(dialog_manager, sent, telegram_id, telegram_id, "0")

    assert "at least 1 adult" in reply
    assert dialog_manager.has_active(telegram_id) is True


def test_unrecognized_sender_cannot_start_registration(tmp_path: Path) -> None:
    db_path, router, dialog_manager, sent = _setup(tmp_path)
    _send_command(router, 999, 999, "/register")

    assert dialog_manager.has_active(999) is False
    assert sent[0][1] == "You're not recognized by this bot yet."


def test_per_user_booking_cap_blocks_at_dialog_start(tmp_path: Path) -> None:
    db_path, router, dialog_manager, sent = _setup(tmp_path, max_bookings_per_user=1)
    telegram_id = 111
    user_id = _register_user(db_path, telegram_id)
    with SqliteStore(db_path) as store:
        from tests.unit.monitor.fakes import make_booking

        SqliteBookingRepository(store).add(make_booking("existing-1"), user_id=user_id)

    _send_command(router, telegram_id, telegram_id, "/register")

    assert dialog_manager.has_active(telegram_id) is False
    assert "maximum this bot" in sent[0][1]


def test_per_user_booking_cap_rechecked_at_save_time(tmp_path: Path) -> None:
    """Cap is enforced again on completion, defending a race where a second
    booking is added by the same user while the dialog is in progress."""
    db_path, router, dialog_manager, sent = _setup(tmp_path, max_bookings_per_user=1)
    telegram_id = 111
    user_id = _register_user(db_path, telegram_id)

    _send_command(router, telegram_id, telegram_id, "/register")
    assert dialog_manager.has_active(telegram_id) is True

    # Simulate a concurrent registration completing while this dialog is open.
    with SqliteStore(db_path) as store:
        from tests.unit.monitor.fakes import make_booking

        SqliteBookingRepository(store).add(make_booking("concurrent-1"), user_id=user_id)

    _drive_to_confirm(dialog_manager, sent, telegram_id, telegram_id)
    final_reply = _send_text(dialog_manager, sent, telegram_id, telegram_id, "yes")

    assert "maximum this bot" in final_reply
    with SqliteStore(db_path) as store:
        bookings = SqliteBookingRepository(store).list_active_for_user(user_id)
    assert len(bookings) == 1  # only the concurrent one, not this dialog's


def test_owner_is_exempt_from_the_booking_cap(tmp_path: Path) -> None:
    db_path, router, dialog_manager, sent = _setup(tmp_path, max_bookings_per_user=1)
    with SqliteStore(db_path) as store:
        owner = SqliteUserRepository(store).get_owner()
        owner_id = owner.user_id
    # Link the owner's telegram id the way an admitted-owner bot session would.
    with SqliteStore(db_path) as store:
        store.conn.execute(
            "UPDATE users SET telegram_user_id = ? WHERE user_id = ?", (222, owner_id)
        )
        store.conn.commit()
        from tests.unit.monitor.fakes import make_booking

        SqliteBookingRepository(store).add(make_booking("existing-1"), user_id=owner_id)

    _send_command(router, 222, 222, "/register")

    assert dialog_manager.has_active(222) is True  # not blocked by the cap
