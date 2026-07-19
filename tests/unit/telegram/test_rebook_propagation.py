from __future__ import annotations

import threading
import uuid
from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from booksaver.domain.post_rebook import (
    HandoffOutcome,
    PostRebookContext,
)
from booksaver.domain.rebook import EventType, RebookEvent
from booksaver.domain.savings import SavingsOpportunity
from booksaver.domain.value_objects import Money, Property
from booksaver.infrastructure.persistence.sqlite_store import (
    SqliteBookingRepository,
    SqliteRebookEventRepository,
    SqliteSavingsRepository,
    SqliteStore,
    SqliteUserRepository,
)
from booksaver.infrastructure.telegram.dialogs import DialogManager
from booksaver.infrastructure.telegram.rebook_gate import (
    PendingPromptRegistry,
    TelegramNavigator,
    run_outcome_followup,
)
from booksaver.infrastructure.telegram.rebook_propagation import (
    reconcile_reported_outcomes,
)

from ..monitor.fakes import make_booking
from .test_rebook_gate import FakeClient, _nonce_from_sent, _wait_until

SOURCE_URL = "https://www.booking.com/hotel/us/example-hotel.html?aid=1"
CANONICAL_URL = "https://www.booking.com/hotel/us/example-hotel.html"


def _fixture(db_path: Path, cancellation: HandoffOutcome) -> tuple[PostRebookContext, int]:
    now = datetime.now(UTC)
    session_id = str(uuid.uuid4())
    opportunity_id = str(uuid.uuid4())
    telegram_user_id = 555
    with SqliteStore(db_path) as store:
        user = SqliteUserRepository(store).get_or_create_by_telegram_id(telegram_user_id)
        booking = replace(
            make_booking(booking_id=str(uuid.uuid4()), ref=SOURCE_URL),
            property=Property("Example Hotel", SOURCE_URL),
        )
        bookings = SqliteBookingRepository(store)
        bookings.add(booking, user_id=user.user_id)
        source = bookings.get_by_id(booking.booking_id)
        assert source is not None
        SqliteSavingsRepository(store).add(
            SavingsOpportunity(
                opportunity_id=opportunity_id,
                booking_id=source.booking_id,
                check_id="check-1",
                baseline_price=source.baseline_price,
                live_price=Money.of("350", "EUR"),
                amount_saved=Money.of("50", "EUR"),
                percent_saved=Decimal("12.5"),
                validated_at=now,
            )
        )
        store.conn.execute(
            "INSERT INTO rebook_sessions "
            "(session_id, opportunity_id, booking_id, state, started_at, ended_at, "
            "end_reason) VALUES (?, ?, ?, 'completed', ?, ?, 'completed')",
            (
                session_id,
                opportunity_id,
                source.booking_id,
                now.isoformat(),
                now.isoformat(),
            ),
        )
        events = SqliteRebookEventRepository(store)
        events.append(
            RebookEvent.record(
                session_id,
                EventType.ACTION_EXECUTED,
                "telegram_handoff kind=cancel chat_id=555 url=https://example.test/cancel",
            )
        )
        events.append(
            RebookEvent.record(
                session_id,
                EventType.ACTION_EXECUTED,
                "telegram_handoff kind=book chat_id=555 url=https://example.test/book",
            )
        )
        store.conn.commit()
    return (
        PostRebookContext(
            user_id=user.user_id,
            session_id=session_id,
            opportunity_id=opportunity_id,
            source_booking=source,
            cancellation_outcome=cancellation,
        ),
        telegram_user_id,
    )


def _reconcile(
    db_path: Path,
    context: PostRebookContext,
    telegram_user_id: int,
    replacement: HandoffOutcome,
) -> tuple[FakeClient, DialogManager]:
    client = FakeClient()
    dialogs = DialogManager()
    reconcile_reported_outcomes(
        client=client,  # type: ignore[arg-type]
        dialog_manager=dialogs,
        db_path=db_path,
        chat_id=telegram_user_id,
        telegram_user_id=telegram_user_id,
        context=context,
        replacement_outcome=replacement,
        is_active=lambda: True,
    )
    return client, dialogs


def test_completed_replacement_collects_actual_facts_then_activates(tmp_path: Path) -> None:
    db_path = tmp_path / "booksaver.db"
    context, telegram_id = _fixture(db_path, HandoffOutcome.COMPLETED)

    client, dialogs = _reconcile(
        db_path, context, telegram_id, HandoffOutcome.COMPLETED
    )

    assert dialogs.active_dialog_name(telegram_id) == "post-rebook:archived"
    assert "NEW Booking.com confirmation ID" in client.sent[-1]["text"]
    with SqliteStore(db_path) as store:
        assert (
            SqliteBookingRepository(store).get_by_id(context.source_booking.booking_id).status.value
            == "archived"
        )

    reply = dialogs.handle_message(telegram_id, telegram_id, "NEW-123")
    assert "Saved confirmation: NEW-123" in reply
    reply = dialogs.handle_message(
        telegram_id,
        telegram_id,
        "https://www.booking.com/hotel/us/different.html",
    )
    assert "different Booking.com property" in reply
    reply = dialogs.handle_message(telegram_id, telegram_id, SOURCE_URL)
    assert CANONICAL_URL in reply
    assert "ACTUAL final all-in total" in reply
    reply = dialogs.handle_message(telegram_id, telegram_id, "387.42 USD")
    assert "Saved actual total: 387.42 USD" in reply
    assert "detected offer" not in reply.lower()
    reply = dialogs.handle_message(telegram_id, telegram_id, "yes")
    assert "Replacement monitoring updated" in reply
    assert "New baseline: 387.42 USD" in reply

    with SqliteStore(db_path) as store:
        booking = SqliteBookingRepository(store).get_by_id(context.source_booking.booking_id)
        assert booking is not None
        assert booking.status.value == "active"
        assert booking.confirmation_id.value == "NEW-123"
        assert booking.baseline_price == Money.of("387.42", "USD")
        assert SqliteSavingsRepository(store).get(context.opportunity_id) is None


def test_completed_cancellation_and_abandoned_replacement_leaves_none_monitored(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "booksaver.db"
    context, telegram_id = _fixture(db_path, HandoffOutcome.COMPLETED)

    client, dialogs = _reconcile(
        db_path, context, telegram_id, HandoffOutcome.ABANDONED
    )

    assert not dialogs.has_active(telegram_id)
    assert "not monitoring a reservation" in client.sent[-1]["text"]
    with SqliteStore(db_path) as store:
        assert SqliteBookingRepository(store).list_active_for_user(context.user_id) == []


def test_abandoned_both_keeps_original_active(tmp_path: Path) -> None:
    db_path = tmp_path / "booksaver.db"
    context, telegram_id = _fixture(db_path, HandoffOutcome.ABANDONED)

    client, dialogs = _reconcile(
        db_path, context, telegram_id, HandoffOutcome.ABANDONED
    )

    assert not dialogs.has_active(telegram_id)
    assert "original reservation remains monitored" in client.sent[-1]["text"]
    with SqliteStore(db_path) as store:
        assert SqliteBookingRepository(store).list_active_for_user(context.user_id) == [
            context.source_booking
        ]
        assert SqliteSavingsRepository(store).get(context.opportunity_id) is not None


def test_declining_replacement_details_preserves_archived_safe_state(tmp_path: Path) -> None:
    db_path = tmp_path / "booksaver.db"
    context, telegram_id = _fixture(db_path, HandoffOutcome.COMPLETED)
    _client, dialogs = _reconcile(
        db_path, context, telegram_id, HandoffOutcome.COMPLETED
    )

    dialogs.handle_message(telegram_id, telegram_id, "NEW-123")
    dialogs.handle_message(telegram_id, telegram_id, SOURCE_URL)
    dialogs.handle_message(telegram_id, telegram_id, "387.42 USD")
    reply = dialogs.handle_message(telegram_id, telegram_id, "no")

    assert "No replacement was activated" in reply
    assert "old reservation remains archived" in reply
    with SqliteStore(db_path) as store:
        assert SqliteBookingRepository(store).list_active_for_user(context.user_id) == []


def test_revocation_before_final_confirmation_prevents_reactivation(tmp_path: Path) -> None:
    db_path = tmp_path / "booksaver.db"
    context, telegram_id = _fixture(db_path, HandoffOutcome.COMPLETED)
    _client, dialogs = _reconcile(
        db_path, context, telegram_id, HandoffOutcome.COMPLETED
    )
    dialogs.handle_message(telegram_id, telegram_id, "NEW-123")
    dialogs.handle_message(telegram_id, telegram_id, SOURCE_URL)
    dialogs.handle_message(telegram_id, telegram_id, "387.42 USD")
    with SqliteStore(db_path) as store:
        store.conn.execute(
            "UPDATE users SET access_state = 'revoked' WHERE user_id = ?", (context.user_id,)
        )
        store.conn.commit()

    reply = dialogs.handle_message(telegram_id, telegram_id, "yes")

    assert "no longer have access" in reply
    with SqliteStore(db_path) as store:
        assert SqliteBookingRepository(store).list_active_for_user(context.user_id) == []


def test_outcome_followup_acknowledges_answers_and_starts_detail_dialog(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "booksaver.db"
    context, telegram_id = _fixture(db_path, HandoffOutcome.COMPLETED)
    client = FakeClient()
    dialogs = DialogManager()
    registry = PendingPromptRegistry()

    with SqliteStore(db_path) as store:
        event_repo = SqliteRebookEventRepository(store)
        navigator = TelegramNavigator(
            client=client,  # type: ignore[arg-type]
            chat_id=telegram_id,
            booking=context.source_booking,
            event_repo=event_repo,
            session_id_box={"session_id": context.session_id},
        )
        navigator.cancel_handoff_sent = True
        navigator.book_handoff_sent = True

        def answer_both() -> None:
            _wait_until(lambda: len(client.sent) >= 1)
            registry.resolve(
                _nonce_from_sent(client.sent[0]), telegram_id, telegram_id, approved=True
            )
            _wait_until(lambda: len(client.sent) >= 2)
            registry.resolve(
                _nonce_from_sent(client.sent[1]), telegram_id, telegram_id, approved=True
            )

        worker = threading.Thread(target=answer_both)
        worker.start()
        run_outcome_followup(
            client=client,  # type: ignore[arg-type]
            registry=registry,
            chat_id=telegram_id,
            telegram_user_id=telegram_id,
            navigator=navigator,
            event_repo=event_repo,
            session_id=context.session_id,
            timeout_seconds=2,
            stop_event=threading.Event(),
            dialog_manager=dialogs,
            db_path=db_path,
            local_user_id=context.user_id,
            source_booking=context.source_booking,
            opportunity_id=context.opportunity_id,
        )
        worker.join(timeout=1)

    assert [edit["text"] for edit in client.edits] == [
        "Recorded: completed.",
        "Recorded: completed.",
    ]
    assert dialogs.active_dialog_name(telegram_id) == "post-rebook:archived"
    assert any("NEW Booking.com confirmation ID" in sent["text"] for sent in client.sent)


def test_unreported_outcomes_remain_distinct_and_keep_source(tmp_path: Path) -> None:
    db_path = tmp_path / "booksaver.db"
    context, telegram_id = _fixture(db_path, HandoffOutcome.UNREPORTED)
    client, dialogs = _reconcile(
        db_path, context, telegram_id, HandoffOutcome.UNREPORTED
    )

    assert not dialogs.has_active(telegram_id)
    assert "unreported" in client.sent[-1]["text"]
    with SqliteStore(db_path) as store:
        assert SqliteBookingRepository(store).list_active_for_user(context.user_id) == [
            context.source_booking
        ]


def test_completed_replacement_warns_when_old_cancellation_unreported(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "booksaver.db"
    context, telegram_id = _fixture(db_path, HandoffOutcome.UNREPORTED)
    _client, dialogs = _reconcile(
        db_path, context, telegram_id, HandoffOutcome.COMPLETED
    )
    dialogs.handle_message(telegram_id, telegram_id, "NEW-123")
    dialogs.handle_message(telegram_id, telegram_id, SOURCE_URL)
    dialogs.handle_message(telegram_id, telegram_id, "387.42 USD")

    reply = dialogs.handle_message(telegram_id, telegram_id, "yes")

    assert "old cancellation was not confirmed" in reply
    with SqliteStore(db_path) as store:
        assert (
            SqliteBookingRepository(store).get_by_id(context.source_booking.booking_id).status.value
            == "active"
        )
