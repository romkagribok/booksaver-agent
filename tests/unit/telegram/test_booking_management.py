from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import pytest

from booksaver.domain.models import Booking
from booksaver.domain.user import UserRole
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
from booksaver.infrastructure.persistence.sqlite_store import (
    SqliteBookingRepository,
    SqliteStore,
    SqliteUserRepository,
)
from booksaver.infrastructure.telegram.booking_management import (
    register_booking_management_commands,
)
from booksaver.infrastructure.telegram.dialogs import DialogManager
from booksaver.infrastructure.telegram.router import (
    CallbackRouter,
    CommandRouter,
    IncomingCallback,
    IncomingCommand,
)


class FakeClient:
    def __init__(self) -> None:
        self.answers: list[tuple[str, str | None]] = []
        self.edits: list[tuple[int, int, str, dict[str, Any] | None]] = []

    def answer_callback_query(self, callback_id: str, text: str | None = None) -> None:
        self.answers.append((callback_id, text))

    def edit_message_text(
        self,
        chat_id: int,
        message_id: int,
        text: str,
        reply_markup: dict[str, Any] | None = None,
    ) -> None:
        self.edits.append((chat_id, message_id, text, reply_markup))


def _booking(booking_id: str, confirmation: str, name: str = "Grand Hotel") -> Booking:
    return Booking(
        booking_id=booking_id,
        platform=Platform.BOOKING_COM,
        product_type=ProductType.HOTEL,
        confirmation_id=ConfirmationId.of(confirmation),
        property=Property(name=name, booking_com_ref="https://booking.com/hotel/grand"),
        stay_dates=StayDates(date(2026, 10, 1), date(2026, 10, 5)),
        room_type=RoomType("Deluxe Double"),
        baseline_price=Money.of("350.00", "EUR"),
        refundability=RefundabilityPolicy(True, "Free cancellation"),
        occupancy=Occupancy(2),
        registered_at=datetime.now(UTC),
    )


def _setup(tmp_path: Path):
    db_path = tmp_path / "booksaver.db"
    router = CommandRouter()
    callbacks = CallbackRouter()
    dialogs = DialogManager()
    client = FakeClient()
    sent: list[tuple[int, str, dict[str, Any] | None]] = []
    register_booking_management_commands(
        router=router,
        callback_router=callbacks,
        dialog_manager=dialogs,
        reply=lambda chat_id, text: sent.append((chat_id, text, None)),
        send=lambda chat_id, text, markup: sent.append((chat_id, text, markup)),
        client=client,  # type: ignore[arg-type]
        db_path=db_path,
    )
    return db_path, router, callbacks, dialogs, client, sent


def _user(db_path: Path, telegram_id: int) -> int:
    with SqliteStore(db_path) as store:
        return SqliteUserRepository(store).get_or_create_by_telegram_id(
            telegram_id, UserRole.USER
        ).user_id


def _add(db_path: Path, booking: Booking, user_id: int) -> None:
    with SqliteStore(db_path) as store:
        SqliteBookingRepository(store).add(booking, user_id=user_id)


def _command(router: CommandRouter, user_id: int, command: str, args: str = "") -> None:
    router.dispatch(IncomingCommand(user_id, user_id, command, args, command))


def _callback(callbacks: CallbackRouter, user_id: int, data: str, suffix: str = "") -> None:
    callbacks.dispatch(
        IncomingCallback(user_id, user_id, f"cb{suffix}", 9, data)
    )


def test_commands_offer_only_caller_owned_bookings_with_safe_payloads(tmp_path: Path) -> None:
    db_path, router, _callbacks, _dialogs, _client, sent = _setup(tmp_path)
    user_a = _user(db_path, 101)
    user_b = _user(db_path, 202)
    own_id = "11111111-1111-4111-8111-111111111111"
    foreign_id = "22222222-2222-4222-8222-222222222222"
    _add(db_path, _booking(own_id, "OWN", "Own Hotel"), user_a)
    _add(db_path, _booking(foreign_id, "FOREIGN", "Foreign Hotel"), user_b)

    _command(router, 101, "/editbooking")
    _command(router, 101, "/deletebooking")

    for _chat_id, _text, markup in sent:
        assert markup is not None
        buttons = [button for row in markup["inline_keyboard"] for button in row]
        assert any("Own Hotel" in button["text"] for button in buttons)
        assert all("Foreign Hotel" not in button["text"] for button in buttons)
        assert all(len(button["callback_data"].encode()) <= 64 for button in buttons)


def test_edit_selection_offers_every_field_as_a_button(tmp_path: Path) -> None:
    db_path, _router, callbacks, _dialogs, client, _sent = _setup(tmp_path)
    user_id = _user(db_path, 101)
    booking_id = "11111111-1111-4111-8111-111111111111"
    _add(db_path, _booking(booking_id, "OWN"), user_id)

    _callback(callbacks, 101, f"bedit:{booking_id}")

    markup = client.edits[-1][3]
    assert markup is not None
    callback_data = {
        button["callback_data"]
        for row in markup["inline_keyboard"]
        for button in row
    }
    assert callback_data == {
        f"bedit:{booking_id}:property",
        f"bedit:{booking_id}:dates",
        f"bedit:{booking_id}:room",
        f"bedit:{booking_id}:price",
        f"bedit:{booking_id}:refund",
        f"bedit:{booking_id}:occupancy",
        f"bedit:{booking_id}:confirmation",
        "bedit:list",
    }
    assert all(len(value.encode()) <= 64 for value in callback_data)


@pytest.mark.parametrize(
    ("field", "answers", "attribute", "expected"),
    [
        ("property", ["Revised Hotel", "-"], "property", "Revised Hotel"),
        ("dates", ["2026-11-02", "2026-11-07"], "dates", date(2026, 11, 2)),
        ("room", ["King Suite"], "room", "King Suite"),
        ("price", ["410.50 USD"], "price", Money.of("410.50", "USD")),
        ("refund", ["New policy", "2026-10-20"], "refund", date(2026, 10, 20)),
        ("occupancy", ["3", "1", "2"], "occupancy", Occupancy(3, 1, 2)),
        ("confirmation", ["NEW-CONF"], "confirmation", "NEW-CONF"),
    ],
)
def test_each_edit_dialog_persists_validated_group_and_preserves_identity(
    tmp_path: Path,
    field: str,
    answers: list[str],
    attribute: str,
    expected: object,
) -> None:
    db_path, _router, callbacks, dialogs, _client, _sent = _setup(tmp_path)
    local_user_id = _user(db_path, 101)
    booking_id = "11111111-1111-4111-8111-111111111111"
    original = _booking(booking_id, "OWN")
    _add(db_path, original, local_user_id)

    _callback(callbacks, 101, f"bedit:{booking_id}:{field}")
    result = ""
    for answer in answers:
        result = dialogs.handle_message(101, 101, answer)

    assert result.startswith("Updated")
    with SqliteStore(db_path) as store:
        repo = SqliteBookingRepository(store)
        updated = repo.get_by_id(booking_id)
        assert updated is not None
        assert updated.booking_id == original.booking_id
        assert updated.registered_at == original.registered_at
        assert repo.get_owner_user_id(booking_id) == local_user_id
    if attribute == "property":
        assert updated.property.name == expected
        assert updated.property.booking_com_ref == original.property.booking_com_ref
    elif attribute == "dates":
        assert updated.stay_dates.check_in == expected
    elif attribute == "room":
        assert updated.room_type.label == expected
    elif attribute == "price":
        assert updated.baseline_price == expected
    elif attribute == "refund":
        assert updated.refundability.deadline == expected
    elif attribute == "occupancy":
        assert updated.occupancy == expected
    else:
        assert updated.confirmation_id.value == expected


def test_invalid_edit_reprompts_and_does_not_persist(tmp_path: Path) -> None:
    db_path, _router, callbacks, dialogs, _client, _sent = _setup(tmp_path)
    local_user_id = _user(db_path, 101)
    booking_id = "11111111-1111-4111-8111-111111111111"
    _add(db_path, _booking(booking_id, "OWN"), local_user_id)

    _callback(callbacks, 101, f"bedit:{booking_id}:dates")
    dialogs.handle_message(101, 101, "2026-11-07")
    response = dialogs.handle_message(101, 101, "2026-11-02")

    assert "must be after check_in" in response
    assert dialogs.has_active(101)
    with SqliteStore(db_path) as store:
        unchanged = SqliteBookingRepository(store).get_by_id(booking_id)
    assert unchanged.stay_dates.check_in == date(2026, 10, 1)


def test_edit_completion_rechecks_ownership(tmp_path: Path) -> None:
    db_path, _router, callbacks, dialogs, _client, _sent = _setup(tmp_path)
    local_user_id = _user(db_path, 101)
    booking_id = "11111111-1111-4111-8111-111111111111"
    _add(db_path, _booking(booking_id, "OWN"), local_user_id)

    _callback(callbacks, 101, f"bedit:{booking_id}:room")
    new_owner_id = _user(db_path, 202)
    with SqliteStore(db_path) as store:
        store.conn.execute(
            "UPDATE bookings SET user_id = ? WHERE booking_id = ?",
            (new_owner_id, booking_id),
        )
        store.conn.commit()
    response = dialogs.handle_message(101, 101, "Stolen Room")

    assert response == "Booking not found."
    with SqliteStore(db_path) as store:
        unchanged = SqliteBookingRepository(store).get_by_id(booking_id)
        assert unchanged is not None
        assert unchanged.room_type.label == "Deluxe Double"


def test_typed_unique_prefix_opens_same_edit_and_delete_screens(tmp_path: Path) -> None:
    db_path, router, _callbacks, _dialogs, _client, sent = _setup(tmp_path)
    local_user_id = _user(db_path, 101)
    booking_id = "11111111-1111-4111-8111-111111111111"
    _add(db_path, _booking(booking_id, "OWN"), local_user_id)

    _command(router, 101, "/editbooking", "11111111")
    _command(router, 101, "/deletebooking", "11111111")

    assert "Choose what to change" in sent[0][1]
    assert "permanently removes" in sent[1][1]


def test_ambiguous_typed_prefix_is_non_disclosing(tmp_path: Path) -> None:
    db_path, router, _callbacks, _dialogs, _client, sent = _setup(tmp_path)
    local_user_id = _user(db_path, 101)
    _add(
        db_path,
        _booking("aaaaaaaa-1111-4111-8111-111111111111", "ONE"),
        local_user_id,
    )
    _add(
        db_path,
        _booking("aaaaaaaa-2222-4222-8222-222222222222", "TWO"),
        local_user_id,
    )

    _command(router, 101, "/editbooking", "aaaaaaaa")

    assert sent[-1][1] == "Booking not found."


def test_confirmation_edit_rejects_another_bookings_confirmation(tmp_path: Path) -> None:
    db_path, _router, callbacks, dialogs, _client, _sent = _setup(tmp_path)
    local_user_id = _user(db_path, 101)
    booking_id = "11111111-1111-4111-8111-111111111111"
    _add(db_path, _booking(booking_id, "ONE"), local_user_id)
    _add(
        db_path,
        _booking("22222222-2222-4222-8222-222222222222", "TWO"),
        local_user_id,
    )

    _callback(callbacks, 101, f"bedit:{booking_id}:confirmation")
    response = dialogs.handle_message(101, 101, "TWO")

    assert "one of your bookings" in response
    assert "TWO" not in response
    with SqliteStore(db_path) as store:
        unchanged = SqliteBookingRepository(store).get_by_id(booking_id)
        assert unchanged is not None
        assert unchanged.confirmation_id.value == "ONE"


def test_confirmation_edit_does_not_disclose_foreign_confirmation(
    tmp_path: Path,
) -> None:
    db_path, _router, callbacks, dialogs, _client, _sent = _setup(tmp_path)
    local_user_id = _user(db_path, 101)
    foreign_user_id = _user(db_path, 202)
    booking_id = "11111111-1111-4111-8111-111111111111"
    _add(db_path, _booking(booking_id, "OWN"), local_user_id)
    _add(
        db_path,
        _booking("22222222-2222-4222-8222-222222222222", "FOREIGN-SECRET"),
        foreign_user_id,
    )

    _callback(callbacks, 101, f"bedit:{booking_id}:confirmation")
    response = dialogs.handle_message(101, 101, "FOREIGN-SECRET")

    assert response == "Booking was not updated. Check the booking details and try again."
    assert "FOREIGN-SECRET" not in response
    assert "already registered" not in response
    with SqliteStore(db_path) as store:
        unchanged = SqliteBookingRepository(store).get_by_id(booking_id)
        assert unchanged is not None
        assert unchanged.confirmation_id.value == "OWN"


def test_delete_cancel_preserves_booking_and_confirm_deletes_it(tmp_path: Path) -> None:
    db_path, _router, callbacks, _dialogs, client, _sent = _setup(tmp_path)
    local_user_id = _user(db_path, 101)
    booking_id = "11111111-1111-4111-8111-111111111111"
    _add(db_path, _booking(booking_id, "OWN"), local_user_id)

    _callback(callbacks, 101, f"bdel:{booking_id}", "-select")
    confirm_markup = client.edits[-1][3]
    assert "does not cancel anything on Booking.com" in client.edits[-1][2]
    assert confirm_markup is not None
    _callback(callbacks, 101, f"bdel:{booking_id}:cancel", "-cancel")
    with SqliteStore(db_path) as store:
        assert SqliteBookingRepository(store).get_by_id(booking_id) is not None

    _callback(callbacks, 101, f"bdel:{booking_id}:confirm", "-confirm")
    with SqliteStore(db_path) as store:
        assert SqliteBookingRepository(store).get_by_id(booking_id) is None
    assert client.answers == [
        ("cb-select", None),
        ("cb-cancel", None),
        ("cb-confirm", None),
    ]


def test_cross_user_and_replayed_callbacks_are_non_disclosing_no_ops(tmp_path: Path) -> None:
    db_path, _router, callbacks, _dialogs, client, _sent = _setup(tmp_path)
    owner_id = _user(db_path, 101)
    _user(db_path, 202)
    booking_id = "11111111-1111-4111-8111-111111111111"
    _add(db_path, _booking(booking_id, "OWN"), owner_id)

    _callback(callbacks, 202, f"bdel:{booking_id}:confirm", "-foreign")
    with SqliteStore(db_path) as store:
        assert SqliteBookingRepository(store).get_by_id(booking_id) is not None
    assert client.edits[-1][2] == "Booking not found."

    _callback(callbacks, 101, f"bdel:{booking_id}:confirm", "-owner")
    _callback(callbacks, 101, f"bdel:{booking_id}:confirm", "-replay")
    assert client.edits[-1][2] == "Booking not found."


def test_active_rebook_blocks_delete_confirmation(tmp_path: Path) -> None:
    db_path, _router, callbacks, _dialogs, client, _sent = _setup(tmp_path)
    local_user_id = _user(db_path, 101)
    booking_id = "11111111-1111-4111-8111-111111111111"
    _add(db_path, _booking(booking_id, "OWN"), local_user_id)
    with SqliteStore(db_path) as store:
        store.conn.execute(
            "INSERT INTO rebook_sessions "
            "(session_id, opportunity_id, booking_id, state, started_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (
                "active",
                "opp",
                booking_id,
                "awaiting_cancel_confirmation",
                datetime.now(UTC).isoformat(),
            ),
        )
        store.conn.commit()

    _callback(callbacks, 101, f"bdel:{booking_id}:confirm")

    assert "active guided rebook" in client.edits[-1][2]
    with SqliteStore(db_path) as store:
        assert SqliteBookingRepository(store).get_by_id(booking_id) is not None


@pytest.mark.parametrize("data", ["bedit:bad:extra:parts", "bdel:bad:extra:parts"])
def test_malformed_callbacks_are_acknowledged_without_mutation(
    tmp_path: Path, data: str
) -> None:
    _db_path, _router, callbacks, _dialogs, client, _sent = _setup(tmp_path)
    _callback(callbacks, 101, data)

    assert client.answers == [("cb", None)]
    assert client.edits[-1][2] == "Booking not found."
