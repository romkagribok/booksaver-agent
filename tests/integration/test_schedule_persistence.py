from __future__ import annotations

import sqlite3
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest

from booksaver.domain.schedule import (
    MissReason,
    ScheduledCheckSlot,
    SlotIdentity,
    SlotStatus,
)
from booksaver.domain.user import UserAccessState
from booksaver.infrastructure.persistence.scheduled_check_slots import (
    IncompleteDailyScheduleError,
    SqliteScheduledCheckSlotRepository,
)
from booksaver.infrastructure.persistence.sqlite_store import (
    SCHEMA_VERSION,
    SqliteStore,
    SqliteUserRepository,
)


def _slot(user_id: int, planned_at: datetime, ordinal: int) -> ScheduledCheckSlot:
    return ScheduledCheckSlot(
        identity=SlotIdentity(
            user_id=user_id,
            schedule_date=planned_at.date(),
            ordinal=ordinal,
        ),
        planned_at=planned_at,
    )


def _add_user(store: SqliteStore, telegram_id: int) -> int:
    return SqliteUserRepository(store).get_or_create_by_telegram_id(telegram_id).user_id


def test_schema_v12_migration_is_additive_and_preserves_v11_state(tmp_path: Path) -> None:
    db_path = tmp_path / "v11.db"
    with SqliteStore(db_path) as store:
        users = SqliteUserRepository(store)
        owner = users.get_owner()
        users.set_encrypted_key(owner.user_id, b"preserved-encrypted-key")
        store.conn.execute(
            """
            INSERT INTO bookings (
                booking_id, platform, product_type, confirmation_id,
                property_name, property_ref, check_in, check_out, room_type,
                baseline_amount, baseline_currency, refundable, refund_note,
                refund_deadline, registered_at, status, occ_adults,
                occ_children, occ_rooms, user_id
            ) VALUES (
                'preserved-booking', 'booking_com', 'hotel', 'CONF-V11',
                'Preserved Hotel', 'preserved-ref', '2026-09-01', '2026-09-03',
                'King', '250.00', 'USD', 1, 'Free cancellation', NULL,
                '2026-08-01T00:00:00+00:00', 'active', 2, 0, 1, ?
            )
            """,
            (owner.user_id,),
        )
        store.conn.commit()

    raw = sqlite3.connect(db_path)
    raw.execute("DROP TABLE scheduled_check_slots")
    raw.execute("UPDATE schema_meta SET version = 11")
    raw.commit()
    raw.close()

    with SqliteStore(db_path) as migrated:
        version = migrated.conn.execute("SELECT MAX(version) FROM schema_meta").fetchone()[0]
        owner = SqliteUserRepository(migrated).get_owner()
        booking = migrated.conn.execute(
            "SELECT confirmation_id, user_id FROM bookings WHERE booking_id = ?",
            ("preserved-booking",),
        ).fetchone()
        indexes = {
            row[1]
            for row in migrated.conn.execute(
                "PRAGMA index_list(scheduled_check_slots)"
            ).fetchall()
        }
        foreign_keys = migrated.conn.execute(
            "PRAGMA foreign_key_list(scheduled_check_slots)"
        ).fetchall()

    assert version == SCHEMA_VERSION == 12
    assert owner.encrypted_key == b"preserved-encrypted-key"
    assert tuple(booking) == ("CONF-V11", owner.user_id)
    assert {"idx_scheduled_slots_due", "idx_scheduled_slots_user_next"} <= indexes
    assert any(row[2] == "users" and row[6] == "CASCADE" for row in foreign_keys)


def test_daily_plan_is_atomic_idempotent_and_rejects_partial_state(tmp_path: Path) -> None:
    db_path = tmp_path / "schedule.db"
    day = date(2026, 8, 2)
    with SqliteStore(db_path) as store:
        user_id = _add_user(store, 2001)
        repo = SqliteScheduledCheckSlotRepository(store)
        original = tuple(
            _slot(user_id, datetime(2026, 8, 2, hour, tzinfo=UTC), ordinal)
            for ordinal, hour in enumerate((2, 11, 20))
        )
        persisted = repo.insert_daily_schedule(original)
        rerolled = tuple(
            _slot(user_id, datetime(2026, 8, 2, hour, tzinfo=UTC), ordinal)
            for ordinal, hour in enumerate((4, 13, 22))
        )

        assert repo.insert_daily_schedule(rerolled) == persisted
        store.conn.execute(
            "DELETE FROM scheduled_check_slots "
            "WHERE user_id = ? AND schedule_date = ? AND ordinal = 2",
            (user_id, day.isoformat()),
        )
        store.conn.commit()

        with pytest.raises(IncompleteDailyScheduleError, match="incomplete"):
            repo.insert_daily_schedule(original)

        assert [slot.ordinal for slot in repo.list_for_user_date(user_id, day)] == [0, 1]

    with SqliteStore(db_path) as reopened:
        assert [
            slot.ordinal
            for slot in SqliteScheduledCheckSlotRepository(reopened).list_for_user_date(
                user_id, day
            )
        ] == [0, 1]


def test_guarded_claim_is_single_winner_and_terminal_slots_do_not_reopen(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "claim.db"
    planned_at = datetime(2026, 8, 2, 10, tzinfo=UTC)
    store_one = SqliteStore(db_path)
    store_two = SqliteStore(db_path)
    store_one.connect()
    try:
        user_id = _add_user(store_one, 2002)
        repo_one = SqliteScheduledCheckSlotRepository(store_one)
        identity = repo_one.insert_daily_schedule((_slot(user_id, planned_at, 0),))[0].identity
        store_two.connect()
        repo_two = SqliteScheduledCheckSlotRepository(store_two)

        claimed = repo_one.claim(
            identity,
            planned_at,
            grace=timedelta(hours=1),
            minimum_spacing=timedelta(hours=2),
        )
        duplicate = repo_two.claim(
            identity,
            planned_at,
            grace=timedelta(hours=1),
            minimum_spacing=timedelta(hours=2),
        )

        assert claimed is not None and claimed.status is SlotStatus.RUNNING
        assert duplicate is None
        assert repo_one.complete(identity, planned_at + timedelta(minutes=10))
        assert not repo_two.complete(identity, planned_at + timedelta(minutes=11))
        assert not repo_two.miss(identity, planned_at + timedelta(minutes=12), MissReason.STOPPING)
        assert (
            repo_two.claim(
                identity,
                planned_at + timedelta(minutes=15),
                grace=timedelta(hours=1),
                minimum_spacing=timedelta(hours=2),
            )
            is None
        )
    finally:
        store_two.close()
        store_one.close()


def test_recovery_marks_indeterminate_running_slot_missed(tmp_path: Path) -> None:
    planned_at = datetime(2026, 8, 2, 9, tzinfo=UTC)
    with SqliteStore(tmp_path / "recovery.db") as store:
        user_id = _add_user(store, 2003)
        repo = SqliteScheduledCheckSlotRepository(store)
        identity = repo.insert_daily_schedule((_slot(user_id, planned_at, 0),))[0].identity
        assert repo.claim(
            identity,
            planned_at,
            grace=timedelta(hours=1),
            minimum_spacing=timedelta(hours=2),
        )

        recovered_at = planned_at + timedelta(minutes=20)
        assert repo.recover_running(recovered_at) == 1
        assert repo.recover_running(recovered_at + timedelta(minutes=1)) == 0
        recovered = repo.list_for_user_date(user_id, planned_at.date())[0]

    assert recovered.status is SlotStatus.MISSED
    assert recovered.started_at == planned_at
    assert recovered.finished_at == recovered_at
    assert recovered.miss_reason is MissReason.RECOVERED_RUNNING


def test_prepare_due_expires_unavailable_and_superseded_slots_without_burst(
    tmp_path: Path,
) -> None:
    now = datetime(2026, 8, 2, 12, tzinfo=UTC)
    with SqliteStore(tmp_path / "due.db") as store:
        owner_id = SqliteUserRepository(store).get_owner().user_id
        second_id = _add_user(store, 2004)
        revoked_id = _add_user(store, 2005)
        users = SqliteUserRepository(store)
        repo = SqliteScheduledCheckSlotRepository(store)
        repo.insert_daily_schedule(
            tuple(
                _slot(owner_id, planned_at, ordinal)
                for ordinal, planned_at in enumerate(
                    (
                        now - timedelta(hours=5),
                        now - timedelta(hours=3),
                        now - timedelta(minutes=30),
                    )
                )
            )
        )
        repo.insert_daily_schedule((_slot(second_id, now - timedelta(minutes=45), 0),))
        repo.insert_daily_schedule((_slot(revoked_id, now - timedelta(minutes=15), 0),))
        users.set_access_state(revoked_id, UserAccessState.REVOKED)

        due = repo.prepare_due(
            now,
            grace=timedelta(hours=4),
            minimum_spacing=timedelta(hours=2),
        )
        rows = store.conn.execute(
            "SELECT user_id, ordinal, status, miss_reason FROM scheduled_check_slots "
            "ORDER BY user_id, ordinal"
        ).fetchall()

    assert [(slot.user_id, slot.planned_at) for slot in due] == [
        (second_id, now - timedelta(minutes=45)),
        (owner_id, now - timedelta(minutes=30)),
    ]
    outcomes = {
        (int(row["user_id"]), int(row["ordinal"])): (row["status"], row["miss_reason"])
        for row in rows
    }
    assert outcomes[(owner_id, 0)] == ("missed", "grace_expired")
    assert outcomes[(owner_id, 1)] == ("missed", "superseded_catch_up")
    assert outcomes[(owner_id, 2)] == ("planned", None)
    assert outcomes[(revoked_id, 0)] == ("missed", "user_unavailable")


def test_actual_spacing_waits_within_grace_then_marks_impossible_slot_missed(
    tmp_path: Path,
) -> None:
    first_at = datetime(2026, 8, 2, 10, tzinfo=UTC)
    second_at = datetime(2026, 8, 2, 11, tzinfo=UTC)
    with SqliteStore(tmp_path / "spacing.db") as store:
        user_id = _add_user(store, 2006)
        repo = SqliteScheduledCheckSlotRepository(store)
        first, second = repo.insert_daily_schedule(
            (_slot(user_id, first_at, 0), _slot(user_id, second_at, 1))
        )
        assert repo.claim(
            first.identity,
            first_at,
            grace=timedelta(hours=1),
            minimum_spacing=timedelta(hours=3),
        )
        assert repo.complete(first.identity, first_at + timedelta(minutes=10))

        assert repo.prepare_due(
            second_at,
            grace=timedelta(hours=1),
            minimum_spacing=timedelta(hours=3),
        ) == ()
        persisted = repo.list_for_user_date(user_id, second_at.date())

    assert persisted[1].identity == second.identity
    assert persisted[1].status is SlotStatus.MISSED
    assert persisted[1].miss_reason is MissReason.SPACING_CONFLICT


def test_next_queries_last_boundary_and_terminal_retention(tmp_path: Path) -> None:
    morning = datetime(2026, 8, 2, 8, tzinfo=UTC)
    midday = datetime(2026, 8, 2, 10, tzinfo=UTC)
    afternoon = datetime(2026, 8, 2, 14, tzinfo=UTC)
    with SqliteStore(tmp_path / "retention.db") as store:
        user_id = _add_user(store, 2007)
        repo = SqliteScheduledCheckSlotRepository(store)
        first, second, third = repo.insert_daily_schedule(
            (
                _slot(user_id, morning, 0),
                _slot(user_id, midday, 1),
                _slot(user_id, afternoon, 2),
            )
        )
        assert repo.claim(first.identity, morning, timedelta(hours=1), timedelta(hours=1))
        assert repo.complete(first.identity, morning + timedelta(minutes=10))
        assert repo.miss(second.identity, midday + timedelta(minutes=10), MissReason.STOPPING)

        prior = repo.last_planned_before(user_id, afternoon)
        assert prior is not None and prior.identity == second.identity
        assert repo.next_planned_for_user(user_id, midday) == third
        assert repo.next_planned_at(midday) == afternoon
        assert repo.prune_terminal(morning + timedelta(minutes=30)) == 1
        assert repo.prune_terminal(midday + timedelta(minutes=30)) == 1
        remaining = repo.list_for_user_date(user_id, morning.date())

    assert remaining == (third,)


def test_user_purge_explicitly_removes_slots_even_without_foreign_keys(tmp_path: Path) -> None:
    with SqliteStore(tmp_path / "purge.db") as store:
        users = SqliteUserRepository(store)
        user = users.get_or_create_by_telegram_id(2008)
        repo = SqliteScheduledCheckSlotRepository(store)
        repo.insert_daily_schedule(
            (_slot(user.user_id, datetime(2026, 8, 2, 12, tzinfo=UTC), 0),)
        )
        store.conn.execute("PRAGMA foreign_keys=OFF")

        users.purge(user.user_id)

        assert store.conn.execute(
            "SELECT COUNT(*) FROM scheduled_check_slots WHERE user_id = ?",
            (user.user_id,),
        ).fetchone()[0] == 0
