from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

from cryptography.fernet import Fernet

from booksaver.daemon.scheduler import Scheduler
from booksaver.domain.account_sync import (
    InventoryCompleteness,
    InventoryDiscoveryResult,
    ReservationLifecycle,
    ReservationObservation,
    SynchronizationTrigger,
)
from booksaver.domain.check_result import CheckResult, ExtractionMethod, FailureCode, FailureReason
from booksaver.domain.mobile_web import (
    GeniusEvidence,
    MobileProfileId,
    PriceSourceProvenance,
)
from booksaver.domain.models import Booking
from booksaver.domain.user_session import UserSessionMetadata, UserSessionSnapshot
from booksaver.domain.value_objects import (
    ConfirmationId,
    DataDirectory,
    Money,
    Platform,
    ProductType,
    Property,
    RefundabilityPolicy,
    RoomType,
    StayDates,
)
from booksaver.infrastructure.persistence.encrypted_session_store import (
    EncryptedUserSessionRepository,
)
from booksaver.infrastructure.persistence.sqlite_store import (
    SqliteAccountReservationRepository,
    SqliteBookingRepository,
    SqliteCheckHistoryRepository,
    SqliteStore,
    SqliteUserRepository,
)
from booksaver.infrastructure.telegram.commands_readonly import register_readonly_commands
from booksaver.infrastructure.telegram.router import (
    CallbackRouter,
    CommandRouter,
    IncomingCallback,
    IncomingCommand,
)


def _register_caller(db_path: Path, telegram_id: int) -> int:
    """Link `telegram_id` to a local user (US-025/US-029 scoping), returning
    its user_id — mirrors what bolt 009's access control does on admission."""
    with SqliteStore(db_path) as store:
        user = SqliteUserRepository(store).get_or_create_by_telegram_id(telegram_id)
        return user.user_id


def _booking(
    booking_id: str = "b-1",
    *,
    check_in: date | None = None,
    refundable: bool = True,
) -> Booking:
    check_in = check_in or datetime.now(UTC).date() + timedelta(days=30)
    return Booking(
        booking_id=booking_id,
        platform=Platform.BOOKING_COM,
        product_type=ProductType.HOTEL,
        confirmation_id=ConfirmationId(f"CONF-{booking_id}"),
        property=Property(name="Hotel Test", booking_com_ref="ref-1"),
        stay_dates=StayDates(check_in=check_in, check_out=check_in + timedelta(days=4)),
        room_type=RoomType(label="Double"),
        baseline_price=Money(amount=Decimal("400.00"), currency="EUR"),
        refundability=RefundabilityPolicy(
            is_refundable=refundable,
            note="free cancellation" if refundable else "non-refundable",
        ),
        registered_at=datetime.now(UTC),
    )


def _observation(
    booking: Booking,
    lifecycle: ReservationLifecycle = ReservationLifecycle.UPCOMING,
) -> ReservationObservation:
    return ReservationObservation(
        remote_id=booking.booking_id,
        lifecycle=lifecycle,
        observed_at=datetime.now(UTC),
        confirmation_id=booking.confirmation_id.value,
        property_name=booking.property.name,
        property_ref=booking.property.booking_com_ref,
        check_in=booking.stay_dates.check_in,
        check_out=booking.stay_dates.check_out,
        room_type=booking.room_type.label,
        booked_total=booking.baseline_price,
        refundable=booking.refundability.is_refundable,
        refund_note=booking.refundability.note,
        occupancy=booking.occupancy,
    )


def _sync_observations(
    db_path: Path,
    user_id: int,
    observations: tuple[ReservationObservation, ...],
) -> None:
    with SqliteStore(db_path) as store:
        SqliteAccountReservationRepository(store).reconcile(
            user_id=user_id,
            run_id=f"run-{user_id}",
            trigger=SynchronizationTrigger.BOOKINGS,
            session_revision="test-session",
            result=InventoryDiscoveryResult(
                observations, InventoryCompleteness.COMPLETE
            ),
            observed_at=datetime.now(UTC),
        )


def _sync_booking(db_path: Path, user_id: int, booking: Booking) -> None:
    _sync_observations(db_path, user_id, (_observation(booking),))


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


class _PickerClient:
    def __init__(self, *, fail_answer: bool = False, fail_edit: bool = False) -> None:
        self.answered: list[str] = []
        self.edits: list[tuple[int, int, str]] = []
        self.fail_answer = fail_answer
        self.fail_edit = fail_edit

    def answer_callback_query(self, callback_query_id: str, text=None):
        if self.fail_answer:
            raise RuntimeError("answer failed")
        self.answered.append(callback_query_id)
        return True

    def edit_message_text(self, chat_id: int, message_id: int, text: str, reply_markup=None):
        if self.fail_edit:
            raise RuntimeError("edit failed")
        self.edits.append((chat_id, message_id, text))
        return {}


def _interactive_setup(
    tmp_path: Path, *, fail_answer: bool = False, fail_edit: bool = False
):
    db_path = tmp_path / "booksaver.db"
    router = CommandRouter()
    callbacks = CallbackRouter()
    client = _PickerClient(fail_answer=fail_answer, fail_edit=fail_edit)
    sent: list[tuple[int, str]] = []
    interactive: list[dict] = []
    register_readonly_commands(
        router=router,
        reply=lambda chat_id, text: sent.append((chat_id, text)),
        db_path=db_path,
        scheduler=Scheduler(),
        callback_router=callbacks,
        client=client,  # type: ignore[arg-type]
        send=lambda chat_id, text, markup: interactive.append(
            {"chat_id": chat_id, "text": text, "reply_markup": markup}
        ),
        is_owner=lambda chat_id: chat_id == 1,
    )
    return db_path, router, callbacks, client, sent, interactive


def test_start_sends_welcome_message(tmp_path: Path) -> None:
    _db, router, sent, _sched = _setup(tmp_path)
    router.dispatch(_cmd("/start"))
    assert len(sent) == 1
    assert "Welcome" in sent[0][1]
    assert "/connect" in sent[0][1]
    assert "/register" not in sent[0][1]


def test_help_lists_all_commands(tmp_path: Path) -> None:
    _db, router, sent, _sched = _setup(tmp_path)
    router.dispatch(_cmd("/help"))
    text = sent[0][1]
    for cmd in (
        "/status",
        "/connect",
        "/bookings",
        "/savings",
        "/checks",
        "/setkey",
        "/deletekey",
        "/admin",
        "/cancelflow",
    ):
        assert cmd in text
    assert "/register" not in text
    assert "/rebook" not in text


def test_status_with_no_database_refuses_unrecognized_sender(tmp_path: Path) -> None:
    _db, router, sent, _sched = _setup(tmp_path)
    router.dispatch(_cmd("/status"))
    assert sent[0][1] == "You're not recognized by this bot."


def test_status_reports_only_callers_booking_count_without_exact_records(tmp_path: Path) -> None:
    db_path, router, sent, _sched = _setup(tmp_path)
    caller_id = _register_caller(db_path, telegram_id=1)
    foreign_id = _register_caller(db_path, telegram_id=2)
    with SqliteStore(db_path) as store:
        repo = SqliteBookingRepository(store)
        repo.add(_booking("caller-booking"), user_id=caller_id)
        repo.add(_booking("foreign-one"), user_id=foreign_id)
        repo.add(_booking("foreign-two"), user_id=foreign_id)
        SqliteCheckHistoryRepository(store).add(
            CheckResult.success(
                booking_id="caller-booking",
                checked_at=datetime.now(UTC),
                live_price=Money(amount=Decimal("350.00"), currency="EUR"),
                extraction_method=ExtractionMethod.DOM,
            )
        )

    router.dispatch(_cmd("/status"))
    text = sent[0][1]
    assert "Your active bookings: 1" in text
    assert "Bookings monitored" not in text
    assert "Hotel Test" not in text
    assert "caller-booking" not in text
    assert "foreign" not in text
    assert "success" not in text


def test_status_reports_missing_caller_session_with_connect_action(
    tmp_path: Path,
) -> None:
    db_path, router, sent, _sched = _setup(tmp_path)
    _register_caller(db_path, telegram_id=1)
    router.dispatch(_cmd("/status"))
    text = sent[0][1]
    assert "Session: missing (encrypted, per-user Booking.com session)" in text
    assert "Action: send /connect to sign in to Booking.com securely." in text
    assert "public rates" not in text
    assert "global" not in text


def test_status_reports_ready_caller_session_without_import_fallback(
    tmp_path: Path, monkeypatch
) -> None:
    db_path, router, sent, _sched = _setup(tmp_path)
    local_user_id = _register_caller(db_path, telegram_id=1)
    secret = Fernet.generate_key().decode("ascii")
    monkeypatch.setenv("BOOKSAVER_SECRET_KEY", secret)
    now = datetime.now(UTC)
    EncryptedUserSessionRepository(
        DataDirectory(path=tmp_path)
    ).save(
        UserSessionSnapshot(
            metadata=UserSessionMetadata.imported(
                owner_user_id=local_user_id,
                platform=Platform.BOOKING_COM,
                imported_at=now,
                expires_at=now + timedelta(days=1),
            ),
            cookies=b"[]",
        )
    )

    router.dispatch(_cmd("/status"))

    text = sent[0][1]
    assert "Session: ready (encrypted, per-user Booking.com session)" in text
    assert "Last validated: not yet" in text
    assert "booksaver auth import" not in text


def test_status_refuses_unrecognized_sender_even_when_other_users_exist(
    tmp_path: Path,
) -> None:
    db_path, router, sent, _sched = _setup(tmp_path)
    _register_caller(db_path, telegram_id=1)

    router.dispatch(_cmd("/status", chat_id=999))

    assert sent[0][1] == "You're not recognized by this bot."


def test_bookings_lists_active_bookings(tmp_path: Path) -> None:
    db_path, router, sent, _sched = _setup(tmp_path)
    user_id = _register_caller(db_path, telegram_id=1)
    _sync_booking(db_path, user_id, _booking())

    router.dispatch(_cmd("/bookings", chat_id=1))
    text = sent[0][1]
    assert "Hotel Test" in text


def test_bookings_only_lists_future_upcoming_reservations(tmp_path: Path) -> None:
    db_path, router, sent, _sched = _setup(tmp_path)
    user_id = _register_caller(db_path, telegram_id=1)
    today = datetime.now(UTC).date()
    future_eligible = _booking("future-eligible", check_in=today + timedelta(days=10))
    future_ineligible = _booking(
        "future-ineligible",
        check_in=today + timedelta(days=20),
        refundable=False,
    )
    past = _booking("past", check_in=today - timedelta(days=10))
    current = _booking("current", check_in=today)
    cancelled = _booking("cancelled", check_in=today + timedelta(days=30))
    _sync_observations(
        db_path,
        user_id,
        (
            _observation(future_eligible),
            _observation(future_ineligible),
            _observation(past, ReservationLifecycle.COMPLETED),
            _observation(current),
            _observation(cancelled, ReservationLifecycle.CANCELLED),
        ),
    )

    router.dispatch(_cmd("/bookings", chat_id=1))

    text = "\n".join(message for _chat_id, message in sent)
    assert "CONF-future-eligible" in text
    assert "CONF-future-ineligible" in text
    assert "ineligible: non-refundable" in text
    assert "CONF-past" not in text
    assert "CONF-current" not in text
    assert "CONF-cancelled" not in text


def test_bookings_with_no_database_reports_none_registered(tmp_path: Path) -> None:
    _db, router, sent, _sched = _setup(tmp_path)
    router.dispatch(_cmd("/bookings"))
    assert sent[0][1] == "No synchronized reservations yet. Send /connect first."


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
    _sync_booking(db_path, user_a, _booking("b-1"))
    _sync_booking(db_path, user_b, _booking("b-2"))

    router.dispatch(_cmd("/bookings", chat_id=1))
    text_a = sent[-1][1]
    assert "CONF-b-1" in text_a
    assert "CONF-b-2" not in text_a

    router.dispatch(_cmd("/bookings", chat_id=2))
    text_b = sent[-1][1]
    assert "CONF-b-2" in text_b
    assert "CONF-b-1" not in text_b


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


def test_checks_without_id_offers_owned_booking_buttons(tmp_path: Path) -> None:
    db_path, router, _callbacks, _client, _sent, interactive = _interactive_setup(tmp_path)
    user_id = _register_caller(db_path, telegram_id=1)
    booking_id = "f42b63a9-00d1-49f1-b0c4-544f5ab60fcf"
    with SqliteStore(db_path) as store:
        SqliteBookingRepository(store).add(_booking(booking_id), user_id=user_id)

    router.dispatch(_cmd("/checks", chat_id=1))

    keyboard = interactive[0]["reply_markup"]["inline_keyboard"]
    assert "Hotel Test" in keyboard[0][0]["text"]
    assert keyboard[0][0]["callback_data"] == f"checks:{booking_id}"
    assert len(keyboard[0][0]["callback_data"].encode()) <= 64


def test_checks_picker_callback_renders_recent_history(tmp_path: Path) -> None:
    db_path, _router, callbacks, client, _sent, _interactive = _interactive_setup(tmp_path)
    user_id = _register_caller(db_path, telegram_id=1)
    booking_id = "f42b63a9-00d1-49f1-b0c4-544f5ab60fcf"
    with SqliteStore(db_path) as store:
        SqliteBookingRepository(store).add(_booking(booking_id), user_id=user_id)
        SqliteCheckHistoryRepository(store).add(
            CheckResult.failure(
                booking_id,
                datetime.now(UTC),
                FailureReason(code=FailureCode.TIMEOUT, detail="page load timed out"),
            )
        )

    callbacks.dispatch(
        IncomingCallback(
            user_id=1,
            chat_id=1,
            callback_query_id="cb-1",
            message_id=99,
            data=f"checks:{booking_id}",
        )
    )

    assert client.answered == ["cb-1"]
    assert "timeout" in client.edits[0][2]


def test_checks_picker_renders_even_when_callback_acknowledgement_fails(
    tmp_path: Path, caplog
) -> None:
    db_path, _router, callbacks, client, _sent, _interactive = _interactive_setup(
        tmp_path, fail_answer=True
    )
    user_id = _register_caller(db_path, telegram_id=1)
    booking_id = "f42b63a9-00d1-49f1-b0c4-544f5ab60fcf"
    with SqliteStore(db_path) as store:
        SqliteBookingRepository(store).add(_booking(booking_id), user_id=user_id)

    callbacks.dispatch(
        IncomingCallback(
            user_id=1,
            chat_id=1,
            callback_query_id="cb-answer-fails",
            message_id=99,
            data=f"checks:{booking_id}",
        )
    )

    assert len(client.edits) == 1
    assert "No checks recorded" in client.edits[0][2]
    assert "Could not answer checks callback" in caplog.text


def test_checks_picker_logs_edit_failure_without_raising(tmp_path: Path, caplog) -> None:
    db_path, _router, callbacks, client, _sent, _interactive = _interactive_setup(
        tmp_path, fail_edit=True
    )
    user_id = _register_caller(db_path, telegram_id=1)
    booking_id = "f42b63a9-00d1-49f1-b0c4-544f5ab60fcf"
    with SqliteStore(db_path) as store:
        SqliteBookingRepository(store).add(_booking(booking_id), user_id=user_id)

    assert callbacks.dispatch(
        IncomingCallback(
            user_id=1,
            chat_id=1,
            callback_query_id="cb-edit-fails",
            message_id=99,
            data=f"checks:{booking_id}",
        )
    )

    assert client.answered == ["cb-edit-fails"]
    assert "Could not edit checks result message 99" in caplog.text


def test_checks_picker_callback_cannot_read_another_users_booking(tmp_path: Path) -> None:
    db_path, _router, callbacks, client, _sent, _interactive = _interactive_setup(tmp_path)
    owner_a = _register_caller(db_path, telegram_id=1)
    _register_caller(db_path, telegram_id=2)
    booking_id = "f42b63a9-00d1-49f1-b0c4-544f5ab60fcf"
    with SqliteStore(db_path) as store:
        SqliteBookingRepository(store).add(_booking(booking_id), user_id=owner_a)

    callbacks.dispatch(
        IncomingCallback(
            user_id=2,
            chat_id=2,
            callback_query_id="cb-x",
            message_id=99,
            data=f"checks:{booking_id}",
        )
    )

    assert "No checks recorded" in client.edits[0][2]


def test_help_hides_admin_for_non_owner_when_owner_check_is_wired(tmp_path: Path) -> None:
    _db, router, _callbacks, _client, sent, _interactive = _interactive_setup(tmp_path)

    router.dispatch(_cmd("/help", chat_id=2))

    assert "/checks" in sent[0][1]
    assert "/admin" not in sent[0][1]


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


def test_checks_reports_authenticated_mobile_source_without_unobserved_genius_status(
    tmp_path: Path,
) -> None:
    db_path, router, sent, _sched = _setup(tmp_path)
    user_id = _register_caller(db_path, telegram_id=1)
    with SqliteStore(db_path) as store:
        SqliteBookingRepository(store).add(_booking(), user_id=user_id)
        SqliteCheckHistoryRepository(store).add(
            CheckResult.success(
                "b-1",
                datetime.now(UTC),
                Money(Decimal("350.00"), "EUR"),
                ExtractionMethod.DOM,
                price_source=PriceSourceProvenance(
                    profile_id=MobileProfileId.ANDROID_CHROMIUM,
                    session_revision_id="revision-7",
                    genius_evidence=GeniusEvidence.NOT_OBSERVED,
                    observed_at=datetime.now(UTC),
                ),
            )
        )

    router.dispatch(_cmd("/checks", args="b-1", chat_id=1))

    text = sent[0][1]
    assert "source=authenticated mobile web (android-chromium)" in text
    assert "Genius" not in text


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
