from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

from booksaver.daemon.scheduler import Scheduler
from booksaver.domain.check_result import CheckResult, ExtractionMethod, FailureCode, FailureReason
from booksaver.domain.models import Booking
from booksaver.domain.value_objects import (
    ConfirmationId,
    Money,
    Platform,
    ProductType,
    Property,
    RefundabilityPolicy,
    RoomType,
    StayDates,
)
from booksaver.infrastructure.persistence.sqlite_store import (
    SqliteBookingRepository,
    SqliteCheckHistoryRepository,
    SqliteStore,
    SqliteUserRepository,
)
from booksaver.infrastructure.telegram.commands_readonly import register_readonly_commands
from booksaver.infrastructure.telegram.router import CommandRouter, IncomingCommand


def _register_caller(db_path: Path, telegram_id: int) -> int:
    """Link `telegram_id` to a local user (US-025/US-029 scoping), returning
    its user_id — mirrors what bolt 009's access control does on admission."""
    with SqliteStore(db_path) as store:
        user = SqliteUserRepository(store).get_or_create_by_telegram_id(telegram_id)
        return user.user_id


def _booking(booking_id: str = "b-1") -> Booking:
    return Booking(
        booking_id=booking_id,
        platform=Platform.BOOKING_COM,
        product_type=ProductType.HOTEL,
        confirmation_id=ConfirmationId(f"CONF-{booking_id}"),
        property=Property(name="Hotel Test", booking_com_ref="ref-1"),
        stay_dates=StayDates(check_in=date(2026, 9, 1), check_out=date(2026, 9, 5)),
        room_type=RoomType(label="Double"),
        baseline_price=Money(amount=Decimal("400.00"), currency="EUR"),
        refundability=RefundabilityPolicy(is_refundable=True, note="free cancellation"),
        registered_at=datetime.now(UTC),
    )


def _cmd(command: str, args: str = "", chat_id: int = 1) -> IncomingCommand:
    return IncomingCommand(
        user_id=chat_id, chat_id=chat_id, command=command, args=args, raw_text=command
    )


def _setup(tmp_path: Path) -> tuple[Path, CommandRouter, list[tuple[int, str]], Scheduler]:
    db_path = tmp_path / "booksaver.db"
    router = CommandRouter()
    sent: list[tuple[int, str]] = []
    scheduler = Scheduler()
    register_readonly_commands(
        router=router,
        reply=lambda chat_id, text: sent.append((chat_id, text)),
        db_path=db_path,
        scheduler=scheduler,
    )
    return db_path, router, sent, scheduler


def test_start_sends_welcome_message(tmp_path: Path) -> None:
    _db, router, sent, _sched = _setup(tmp_path)
    router.dispatch(_cmd("/start"))
    assert len(sent) == 1
    assert "Welcome" in sent[0][1]
    assert "/register" in sent[0][1]


def test_help_lists_all_commands(tmp_path: Path) -> None:
    _db, router, sent, _sched = _setup(tmp_path)
    router.dispatch(_cmd("/help"))
    text = sent[0][1]
    for cmd in (
        "/status",
        "/register",
        "/bookings",
        "/savings",
        "/checks",
        "/rebook",
        "/setkey",
        "/deletekey",
        "/admin",
        "/cancelflow",
    ):
        assert cmd in text


def test_status_with_no_database_reports_no_bookings(tmp_path: Path) -> None:
    _db, router, sent, _sched = _setup(tmp_path)
    router.dispatch(_cmd("/status"))
    text = sent[0][1]
    assert "No bookings registered yet." in text
    assert "Next scheduled run: pending first tick" in text


def test_status_reports_bookings_and_recent_check(tmp_path: Path) -> None:
    db_path, router, sent, _sched = _setup(tmp_path)
    with SqliteStore(db_path) as store:
        SqliteBookingRepository(store).add(_booking())
        SqliteCheckHistoryRepository(store).add(
            CheckResult.success(
                booking_id="b-1",
                checked_at=datetime.now(UTC),
                live_price=Money(amount=Decimal("350.00"), currency="EUR"),
                extraction_method=ExtractionMethod.DOM,
            )
        )

    router.dispatch(_cmd("/status"))
    text = sent[0][1]
    assert "Bookings monitored: 1" in text
    assert "success" in text


def test_status_reports_logged_out_session_mode_by_default(tmp_path: Path) -> None:
    _db, router, sent, _sched = _setup(tmp_path)
    router.dispatch(_cmd("/status"))
    assert "Session: logged out (public rates" in sent[0][1]


def test_bookings_lists_active_bookings(tmp_path: Path) -> None:
    db_path, router, sent, _sched = _setup(tmp_path)
    user_id = _register_caller(db_path, telegram_id=1)
    with SqliteStore(db_path) as store:
        SqliteBookingRepository(store).add(_booking(), user_id=user_id)

    router.dispatch(_cmd("/bookings", chat_id=1))
    text = sent[0][1]
    assert "Hotel Test" in text


def test_bookings_with_no_database_reports_none_registered(tmp_path: Path) -> None:
    _db, router, sent, _sched = _setup(tmp_path)
    router.dispatch(_cmd("/bookings"))
    assert sent[0][1] == "No bookings registered yet."


def test_bookings_unrecognized_sender_gets_polite_refusal(tmp_path: Path) -> None:
    db_path, router, sent, _sched = _setup(tmp_path)
    user_id = _register_caller(db_path, telegram_id=1)
    with SqliteStore(db_path) as store:
        SqliteBookingRepository(store).add(_booking(), user_id=user_id)

    router.dispatch(_cmd("/bookings", chat_id=999))  # never linked to a user
    assert sent[0][1] == "You're not recognized by this bot."


def test_bookings_only_shows_the_calling_users_own_bookings(tmp_path: Path) -> None:
    db_path, router, sent, _sched = _setup(tmp_path)
    user_a = _register_caller(db_path, telegram_id=1)
    user_b = _register_caller(db_path, telegram_id=2)
    with SqliteStore(db_path) as store:
        repo = SqliteBookingRepository(store)
        repo.add(_booking("b-1"), user_id=user_a)
        repo.add(_booking("b-2"), user_id=user_b)

    router.dispatch(_cmd("/bookings", chat_id=1))
    text_a = sent[-1][1]
    assert "b-1" in text_a or "b-1"[:8] in text_a
    assert "b-2"[:8] not in text_a

    router.dispatch(_cmd("/bookings", chat_id=2))
    text_b = sent[-1][1]
    assert "b-2"[:8] in text_b
    assert "b-1"[:8] not in text_b


def test_savings_with_no_database_reports_none_detected(tmp_path: Path) -> None:
    _db, router, sent, _sched = _setup(tmp_path)
    router.dispatch(_cmd("/savings"))
    assert sent[0][1] == "No savings opportunities detected yet."


def test_savings_unrecognized_sender_gets_polite_refusal(tmp_path: Path) -> None:
    db_path, router, sent, _sched = _setup(tmp_path)
    _register_caller(db_path, telegram_id=1)

    router.dispatch(_cmd("/savings", chat_id=999))
    assert sent[0][1] == "You're not recognized by this bot."


def test_checks_requires_a_booking_id_argument(tmp_path: Path) -> None:
    _db, router, sent, _sched = _setup(tmp_path)
    router.dispatch(_cmd("/checks", args=""))
    assert sent[0][1] == "Usage: /checks <booking_id>"


def test_checks_reports_recent_history_including_failures(tmp_path: Path) -> None:
    db_path, router, sent, _sched = _setup(tmp_path)
    user_id = _register_caller(db_path, telegram_id=1)
    with SqliteStore(db_path) as store:
        SqliteBookingRepository(store).add(_booking(), user_id=user_id)
        history = SqliteCheckHistoryRepository(store)
        history.add(
            CheckResult.failure(
                "b-1",
                datetime.now(UTC),
                FailureReason(code=FailureCode.TIMEOUT, detail="page load timed out"),
            )
        )

    router.dispatch(_cmd("/checks", args="b-1", chat_id=1))
    text = sent[0][1]
    assert "timeout" in text


def test_checks_accepts_unique_displayed_booking_id_prefix(tmp_path: Path) -> None:
    db_path, router, sent, _sched = _setup(tmp_path)
    user_id = _register_caller(db_path, telegram_id=1)
    full_id = "f42b63a9-00d1-49f1-b0c4-544f5ab60fcf"
    with SqliteStore(db_path) as store:
        SqliteBookingRepository(store).add(_booking(full_id), user_id=user_id)
        SqliteCheckHistoryRepository(store).add(
            CheckResult.failure(
                full_id,
                datetime.now(UTC),
                FailureReason(code=FailureCode.AGENT_GAVE_UP, detail="calendar drift"),
            )
        )

    router.dispatch(_cmd("/checks", args="f42b63a9", chat_id=1))

    assert "agent_gave_up" in sent[0][1]


def test_checks_rejects_ambiguous_displayed_booking_id_prefix(tmp_path: Path) -> None:
    db_path, router, sent, _sched = _setup(tmp_path)
    user_id = _register_caller(db_path, telegram_id=1)
    with SqliteStore(db_path) as store:
        repo = SqliteBookingRepository(store)
        repo.add(_booking("f42b63a9-0000-4000-8000-000000000001"), user_id=user_id)
        repo.add(_booking("f42b63a9-0000-4000-8000-000000000002"), user_id=user_id)

    router.dispatch(_cmd("/checks", args="f42b63a9", chat_id=1))

    assert sent[0][1] == "No checks recorded for booking 'f42b63a9'."


def test_checks_rejects_prefix_shorter_than_displayed_id(tmp_path: Path) -> None:
    db_path, router, sent, _sched = _setup(tmp_path)
    user_id = _register_caller(db_path, telegram_id=1)
    with SqliteStore(db_path) as store:
        SqliteBookingRepository(store).add(
            _booking("f42b63a9-00d1-49f1-b0c4-544f5ab60fcf"), user_id=user_id
        )

    router.dispatch(_cmd("/checks", args="f42b63a", chat_id=1))

    assert sent[0][1] == "No checks recorded for booking 'f42b63a'."


def test_checks_does_not_resolve_another_users_prefix(tmp_path: Path) -> None:
    db_path, router, sent, _sched = _setup(tmp_path)
    user_a = _register_caller(db_path, telegram_id=1)
    _register_caller(db_path, telegram_id=2)
    full_id = "f42b63a9-00d1-49f1-b0c4-544f5ab60fcf"
    with SqliteStore(db_path) as store:
        SqliteBookingRepository(store).add(_booking(full_id), user_id=user_a)

    router.dispatch(_cmd("/checks", args="f42b63a9", chat_id=2))

    assert sent[0][1] == "No checks recorded for booking 'f42b63a9'."


def test_checks_unknown_booking_reports_none_found(tmp_path: Path) -> None:
    db_path, router, sent, _sched = _setup(tmp_path)
    user_id = _register_caller(db_path, telegram_id=1)
    with SqliteStore(db_path) as store:
        SqliteBookingRepository(store).add(_booking(), user_id=user_id)

    router.dispatch(_cmd("/checks", args="unknown-id", chat_id=1))
    assert "No checks recorded for booking" in sent[0][1]


def test_checks_another_users_booking_reports_none_found(tmp_path: Path) -> None:
    """Same not-found message for someone else's booking id — no oracle."""
    db_path, router, sent, _sched = _setup(tmp_path)
    user_a = _register_caller(db_path, telegram_id=1)
    user_b = _register_caller(db_path, telegram_id=2)
    with SqliteStore(db_path) as store:
        SqliteBookingRepository(store).add(_booking("b-1"), user_id=user_a)
        history = SqliteCheckHistoryRepository(store)
        history.add(
            CheckResult.failure(
                "b-1",
                datetime.now(UTC),
                FailureReason(code=FailureCode.TIMEOUT, detail="page load timed out"),
            )
        )
    del user_b

    router.dispatch(_cmd("/checks", args="b-1", chat_id=2))
    assert sent[0][1] == "No checks recorded for booking 'b-1'."
