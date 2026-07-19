from __future__ import annotations

import json
import uuid
from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from booksaver.domain.models import BookingStatus
from booksaver.domain.post_rebook import (
    HandoffOutcome,
    MonitoringDisposition,
    PostRebookContext,
    PostRebookRejected,
    PostRebookRejection,
    ReplacementFacts,
)
from booksaver.domain.rebook import EventType, RebookEvent
from booksaver.domain.savings import SavingsOpportunity
from booksaver.domain.value_objects import ConfirmationId, Money, Property
from booksaver.infrastructure.persistence.sqlite_store import (
    SqliteBookingRepository,
    SqliteRebookEventRepository,
    SqliteSavingsRepository,
    SqliteStore,
    SqliteUserRepository,
)
from tests.unit.monitor.fakes import make_booking

SOURCE_URL = "https://www.booking.com/hotel/us/example-hotel.html?aid=1&sid=secret"
CANONICAL_URL = "https://www.booking.com/hotel/us/example-hotel.html"


def _setup(db_path: Path) -> PostRebookContext:
    now = datetime.now(UTC)
    opportunity_id = str(uuid.uuid4())
    session_id = str(uuid.uuid4())
    with SqliteStore(db_path) as store:
        users = SqliteUserRepository(store)
        user = users.get_or_create_by_telegram_id(555)
        bookings = SqliteBookingRepository(store)
        booking = replace(
            make_booking(booking_id=str(uuid.uuid4()), ref=SOURCE_URL),
            property=Property("Example Hotel", SOURCE_URL),
        )
        bookings.add(booking, user_id=user.user_id)
        source = bookings.get_by_id(booking.booking_id)
        assert source is not None

        SqliteSavingsRepository(store).add(
            SavingsOpportunity(
                opportunity_id=opportunity_id,
                booking_id=source.booking_id,
                check_id="check-before-rebook",
                baseline_price=source.baseline_price,
                live_price=Money.of("350.00", "EUR"),
                amount_saved=Money.of("50.00", "EUR"),
                percent_saved=Decimal("12.50"),
                validated_at=now,
            )
        )
        store.conn.execute(
            "INSERT INTO check_history "
            "(check_id, booking_id, checked_at, outcome, extraction_method, "
            "live_amount, live_currency) VALUES (?, ?, ?, 'success', 'dom', ?, ?)",
            ("check-before-rebook", source.booking_id, now.isoformat(), "350", "EUR"),
        )
        store.conn.execute(
            "INSERT INTO check_traces (check_id, booking_id, created_at, trace_json) "
            "VALUES (?, ?, ?, ?)",
            (
                "check-before-rebook",
                source.booking_id,
                now.isoformat(),
                json.dumps({"events": []}),
            ),
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
    return PostRebookContext(
        user_id=user.user_id,
        session_id=session_id,
        opportunity_id=opportunity_id,
        source_booking=source,
        cancellation_outcome=HandoffOutcome.COMPLETED,
    )


def _facts(confirmation: str = "NEW-CONFIRMATION") -> ReplacementFacts:
    return ReplacementFacts(
        confirmation_id=ConfirmationId.of(confirmation),
        property_ref=CANONICAL_URL,
        actual_total=Money.of("387.42", "USD"),
    )


def test_activation_updates_stable_booking_with_actual_facts_and_preserves_history(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "booksaver.db"
    context = _setup(db_path)

    with SqliteStore(db_path) as store:
        result = SqliteBookingRepository(store).activate_replacement(context, _facts())

        assert result.disposition is MonitoringDisposition.REPLACEMENT_ACTIVE
        assert result.booking.booking_id == context.source_booking.booking_id
        assert result.booking.confirmation_id.value == "NEW-CONFIRMATION"
        assert result.booking.property.booking_com_ref == CANONICAL_URL
        assert result.booking.baseline_price == Money.of("387.42", "USD")
        assert result.booking.baseline_price != Money.of("350.00", "EUR")
        assert result.booking.stay_dates == context.source_booking.stay_dates
        assert result.booking.room_type == context.source_booking.room_type
        assert result.booking.refundability == context.source_booking.refundability
        assert result.booking.occupancy == context.source_booking.occupancy

        assert SqliteSavingsRepository(store).get(context.opportunity_id) is None
        assert store.conn.execute(
            "SELECT COUNT(*) FROM check_history WHERE booking_id = ?",
            (context.source_booking.booking_id,),
        ).fetchone()[0] == 1
        assert store.conn.execute(
            "SELECT COUNT(*) FROM check_traces WHERE booking_id = ?",
            (context.source_booking.booking_id,),
        ).fetchone()[0] == 1
        assert store.conn.execute(
            "SELECT COUNT(*) FROM rebook_sessions WHERE booking_id = ?",
            (context.source_booking.booking_id,),
        ).fetchone()[0] == 1
        details = [
            row[0]
            for row in store.conn.execute(
                "SELECT detail FROM rebook_events WHERE session_id = ? ORDER BY id",
                (context.session_id,),
            )
        ]
        assert details[-1].startswith("post_rebook disposition=replacement_active")


def test_reported_cancellation_archives_and_invalidates_savings(tmp_path: Path) -> None:
    db_path = tmp_path / "booksaver.db"
    context = _setup(db_path)

    with SqliteStore(db_path) as store:
        repo = SqliteBookingRepository(store)
        result = repo.archive_cancelled_source(context)

        assert result.disposition is MonitoringDisposition.SOURCE_ARCHIVED
        assert repo.get_by_id(context.source_booking.booking_id).status is BookingStatus.ARCHIVED
        assert SqliteSavingsRepository(store).get(context.opportunity_id) is None
        assert store.conn.execute(
            "SELECT COUNT(*) FROM check_history WHERE booking_id = ?",
            (context.source_booking.booking_id,),
        ).fetchone()[0] == 1


def test_archived_source_can_be_reactivated_as_replacement(tmp_path: Path) -> None:
    db_path = tmp_path / "booksaver.db"
    context = _setup(db_path)

    with SqliteStore(db_path) as store:
        repo = SqliteBookingRepository(store)
        repo.archive_cancelled_source(context)
        result = repo.activate_replacement(context, _facts())

        assert result.booking.status is BookingStatus.ACTIVE
        assert repo.list_active_for_user(context.user_id) == [result.booking]


def test_archive_and_activation_are_idempotent_without_duplicate_audit(tmp_path: Path) -> None:
    db_path = tmp_path / "booksaver.db"
    context = _setup(db_path)

    with SqliteStore(db_path) as store:
        repo = SqliteBookingRepository(store)
        assert repo.archive_cancelled_source(context).disposition is (
            MonitoringDisposition.SOURCE_ARCHIVED
        )
        assert repo.archive_cancelled_source(context).disposition is (
            MonitoringDisposition.SOURCE_ALREADY_ARCHIVED
        )
        assert repo.activate_replacement(context, _facts()).disposition is (
            MonitoringDisposition.REPLACEMENT_ACTIVE
        )
        assert repo.activate_replacement(context, _facts()).disposition is (
            MonitoringDisposition.REPLACEMENT_ALREADY_ACTIVE
        )
        count = store.conn.execute(
            "SELECT COUNT(*) FROM rebook_events WHERE session_id = ? "
            "AND detail LIKE 'post_rebook disposition=%'",
            (context.session_id,),
        ).fetchone()[0]
        assert count == 2


def test_revoked_user_rejects_activation_without_mutation(tmp_path: Path) -> None:
    db_path = tmp_path / "booksaver.db"
    context = _setup(db_path)
    with SqliteStore(db_path) as store:
        store.conn.execute(
            "UPDATE users SET access_state = 'revoked' WHERE user_id = ?", (context.user_id,)
        )
        store.conn.commit()
        repo = SqliteBookingRepository(store)

        with pytest.raises(PostRebookRejected) as raised:
            repo.activate_replacement(context, _facts())

        assert raised.value.reason is PostRebookRejection.ACCESS_LOST
        assert repo.get_by_id(context.source_booking.booking_id) == context.source_booking
        assert SqliteSavingsRepository(store).get(context.opportunity_id) is not None


def test_foreign_owner_context_rejects_without_mutation(tmp_path: Path) -> None:
    db_path = tmp_path / "booksaver.db"
    context = _setup(db_path)
    with SqliteStore(db_path) as store:
        stranger = SqliteUserRepository(store).get_or_create_by_telegram_id(999)
        foreign_context = replace(context, user_id=stranger.user_id)
        repo = SqliteBookingRepository(store)

        with pytest.raises(PostRebookRejected) as raised:
            repo.activate_replacement(foreign_context, _facts())

        assert raised.value.reason is PostRebookRejection.STALE
        assert repo.get_by_id(context.source_booking.booking_id) == context.source_booking
        assert SqliteSavingsRepository(store).get(context.opportunity_id) is not None


@pytest.mark.parametrize("missing", ["session", "book_handoff"])
def test_missing_audit_precondition_rejects_without_mutation(
    tmp_path: Path, missing: str
) -> None:
    db_path = tmp_path / "booksaver.db"
    context = _setup(db_path)
    with SqliteStore(db_path) as store:
        if missing == "session":
            context = replace(context, session_id="missing-session")
        else:
            store.conn.execute(
                "DELETE FROM rebook_events WHERE session_id = ? "
                "AND detail LIKE 'telegram_handoff kind=book %'",
                (context.session_id,),
            )
            store.conn.commit()
        repo = SqliteBookingRepository(store)

        with pytest.raises(PostRebookRejected) as raised:
            repo.activate_replacement(context, _facts())

        assert raised.value.reason is PostRebookRejection.STALE
        assert repo.get_by_id(context.source_booking.booking_id) == context.source_booking
        assert SqliteSavingsRepository(store).get(context.opportunity_id) is not None


def test_duplicate_confirmation_rolls_back_booking_savings_and_audit(tmp_path: Path) -> None:
    db_path = tmp_path / "booksaver.db"
    context = _setup(db_path)
    with SqliteStore(db_path) as store:
        repo = SqliteBookingRepository(store)
        other = replace(
            make_booking(booking_id=str(uuid.uuid4()), ref=CANONICAL_URL),
            confirmation_id=ConfirmationId.of("DUPLICATE"),
        )
        repo.add(other, user_id=context.user_id)
        before_events = store.conn.execute(
            "SELECT COUNT(*) FROM rebook_events WHERE session_id = ?",
            (context.session_id,),
        ).fetchone()[0]

        with pytest.raises(PostRebookRejected) as raised:
            repo.activate_replacement(context, _facts("DUPLICATE"))

        assert raised.value.reason is PostRebookRejection.CONFLICT
        assert repo.get_by_id(context.source_booking.booking_id) == context.source_booking
        assert SqliteSavingsRepository(store).get(context.opportunity_id) is not None
        after_events = store.conn.execute(
            "SELECT COUNT(*) FROM rebook_events WHERE session_id = ?",
            (context.session_id,),
        ).fetchone()[0]
        assert after_events == before_events
