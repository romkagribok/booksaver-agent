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
)
from booksaver.infrastructure.telegram.commands_readonly import register_readonly_commands
from booksaver.infrastructure.telegram.router import CommandRouter, IncomingCommand


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


def test_help_lists_all_commands(tmp_path: Path) -> None:
    _db, router, sent, _sched = _setup(tmp_path)
    router.dispatch(_cmd("/help"))
    text = sent[0][1]
    for cmd in ("/status", "/bookings", "/savings", "/checks", "/cancelflow"):
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


def test_bookings_lists_active_bookings(tmp_path: Path) -> None:
    db_path, router, sent, _sched = _setup(tmp_path)
    with SqliteStore(db_path) as store:
        SqliteBookingRepository(store).add(_booking())

    router.dispatch(_cmd("/bookings"))
    text = sent[0][1]
    assert "Hotel Test" in text


def test_bookings_with_no_database_reports_none_registered(tmp_path: Path) -> None:
    _db, router, sent, _sched = _setup(tmp_path)
    router.dispatch(_cmd("/bookings"))
    assert sent[0][1] == "No bookings registered yet."


def test_savings_with_no_database_reports_none_detected(tmp_path: Path) -> None:
    _db, router, sent, _sched = _setup(tmp_path)
    router.dispatch(_cmd("/savings"))
    assert sent[0][1] == "No savings opportunities detected yet."


def test_checks_requires_a_booking_id_argument(tmp_path: Path) -> None:
    _db, router, sent, _sched = _setup(tmp_path)
    router.dispatch(_cmd("/checks", args=""))
    assert sent[0][1] == "Usage: /checks <booking_id>"


def test_checks_reports_recent_history_including_failures(tmp_path: Path) -> None:
    db_path, router, sent, _sched = _setup(tmp_path)
    with SqliteStore(db_path) as store:
        SqliteBookingRepository(store).add(_booking())
        history = SqliteCheckHistoryRepository(store)
        history.add(
            CheckResult.failure(
                "b-1",
                datetime.now(UTC),
                FailureReason(code=FailureCode.TIMEOUT, detail="page load timed out"),
            )
        )

    router.dispatch(_cmd("/checks", args="b-1"))
    text = sent[0][1]
    assert "timeout" in text


def test_checks_unknown_booking_reports_none_found(tmp_path: Path) -> None:
    db_path, router, sent, _sched = _setup(tmp_path)
    with SqliteStore(db_path) as store:
        SqliteBookingRepository(store).add(_booking())

    router.dispatch(_cmd("/checks", args="unknown-id"))
    assert "No checks recorded for booking" in sent[0][1]
