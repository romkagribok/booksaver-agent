from __future__ import annotations

import sqlite3
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from datetime import UTC, date, datetime, timedelta

from booksaver.domain.schedule import (
    MissReason,
    ScheduledCheckSlot,
    SlotIdentity,
    SlotStatus,
)
from booksaver.infrastructure.persistence.sqlite_store import SqliteStore


class IncompleteDailyScheduleError(RuntimeError):
    """Raised when a persisted user/date aggregate is only partly present."""


def _utc_text(value: datetime) -> str:
    if value.tzinfo is None or value.utcoffset() != timedelta(0):
        raise ValueError("Schedule timestamps must be timezone-aware UTC datetimes")
    return value.astimezone(UTC).isoformat()


def _positive_duration(value: timedelta, name: str) -> None:
    if value <= timedelta(0):
        raise ValueError(f"{name} must be positive")


class SqliteScheduledCheckSlotRepository:
    """SQLite lifecycle boundary for persisted randomized schedule slots.

    Every multi-step mutation takes an immediate transaction. This serializes
    planning and guarded claims across connections without extending a lock
    across browser work.
    """

    def __init__(self, store: SqliteStore) -> None:
        self._store = store

    @contextmanager
    def _immediate_transaction(self) -> Iterator[sqlite3.Connection]:
        conn = self._store.conn
        if conn.in_transaction:
            raise RuntimeError(
                "Scheduled-slot operations require a clean SQLite transaction boundary"
            )
        conn.execute("BEGIN IMMEDIATE")
        try:
            yield conn
        except Exception:
            conn.rollback()
            raise
        else:
            conn.commit()

    def list_for_user_date(
        self, user_id: int, schedule_date: date
    ) -> tuple[ScheduledCheckSlot, ...]:
        rows = self._store.conn.execute(
            "SELECT * FROM scheduled_check_slots "
            "WHERE user_id = ? AND schedule_date = ? ORDER BY ordinal",
            (user_id, schedule_date.isoformat()),
        ).fetchall()
        return tuple(self._row_to_slot(row) for row in rows)

    def insert_daily_schedule(
        self, slots: Sequence[ScheduledCheckSlot]
    ) -> tuple[ScheduledCheckSlot, ...]:
        proposed = tuple(slots)
        if not proposed:
            raise ValueError("A daily schedule must contain at least one slot")

        user_id = proposed[0].user_id
        schedule_date = proposed[0].schedule_date
        expected_ordinals = tuple(range(len(proposed)))
        actual_ordinals = tuple(slot.ordinal for slot in proposed)
        if actual_ordinals != expected_ordinals:
            raise ValueError("Daily schedule ordinals must be contiguous from zero")
        if any(
            slot.user_id != user_id or slot.schedule_date != schedule_date
            for slot in proposed
        ):
            raise ValueError("All daily schedule slots must belong to one user and UTC date")
        if any(
            slot.status is not SlotStatus.PLANNED
            or slot.started_at is not None
            or slot.finished_at is not None
            or slot.miss_reason is not None
            for slot in proposed
        ):
            raise ValueError("New daily schedules may contain only pristine planned slots")
        for slot in proposed:
            _utc_text(slot.planned_at)
        if any(
            current.planned_at >= following.planned_at
            for current, following in zip(proposed, proposed[1:], strict=False)
        ):
            raise ValueError("Daily schedule planned times must be strictly increasing")

        with self._immediate_transaction() as conn:
            existing_rows = conn.execute(
                "SELECT * FROM scheduled_check_slots "
                "WHERE user_id = ? AND schedule_date = ? ORDER BY ordinal",
                (user_id, schedule_date.isoformat()),
            ).fetchall()
            if existing_rows:
                persisted_ordinals = tuple(int(row["ordinal"]) for row in existing_rows)
                if persisted_ordinals != expected_ordinals:
                    raise IncompleteDailyScheduleError(
                        "Persisted daily schedule is incomplete; refusing to reroll it"
                    )
                return tuple(self._row_to_slot(row) for row in existing_rows)

            active = conn.execute(
                "SELECT 1 FROM users WHERE user_id = ? AND access_state = 'active'",
                (user_id,),
            ).fetchone()
            if active is None:
                raise ValueError(f"Cannot plan schedule for unavailable user '{user_id}'")

            created_at = datetime.now(UTC).isoformat()
            conn.executemany(
                """
                INSERT INTO scheduled_check_slots (
                    user_id, schedule_date, ordinal, planned_at, status,
                    started_at, finished_at, miss_reason, created_at
                ) VALUES (?, ?, ?, ?, ?, NULL, NULL, NULL, ?)
                """,
                [
                    (
                        slot.user_id,
                        slot.schedule_date.isoformat(),
                        slot.ordinal,
                        _utc_text(slot.planned_at),
                        SlotStatus.PLANNED.value,
                        created_at,
                    )
                    for slot in proposed
                ],
            )

        return self.list_for_user_date(user_id, schedule_date)

    def last_planned_before(
        self, user_id: int, instant: datetime
    ) -> ScheduledCheckSlot | None:
        row = self._store.conn.execute(
            "SELECT * FROM scheduled_check_slots "
            "WHERE user_id = ? AND planned_at < ? "
            "ORDER BY planned_at DESC, ordinal DESC LIMIT 1",
            (user_id, _utc_text(instant)),
        ).fetchone()
        return self._row_to_slot(row) if row is not None else None

    def recover_running(self, now: datetime) -> int:
        now_text = _utc_text(now)
        with self._immediate_transaction() as conn:
            cursor = conn.execute(
                "UPDATE scheduled_check_slots "
                "SET status = ?, finished_at = ?, miss_reason = ? "
                "WHERE status = ?",
                (
                    SlotStatus.MISSED.value,
                    now_text,
                    MissReason.RECOVERED_RUNNING.value,
                    SlotStatus.RUNNING.value,
                ),
            )
            return cursor.rowcount

    def prepare_due(
        self,
        now: datetime,
        grace: timedelta,
        minimum_spacing: timedelta,
    ) -> tuple[ScheduledCheckSlot, ...]:
        """Terminalize stale work and return at most one claimable slot/user."""
        _positive_duration(grace, "grace")
        _positive_duration(minimum_spacing, "minimum_spacing")
        now_text = _utc_text(now)
        cutoff_text = _utc_text(now - grace)

        with self._immediate_transaction() as conn:
            conn.execute(
                """
                UPDATE scheduled_check_slots
                SET status = ?, finished_at = ?, miss_reason = ?
                WHERE status = ?
                  AND planned_at <= ?
                  AND NOT EXISTS (
                      SELECT 1 FROM users
                      WHERE users.user_id = scheduled_check_slots.user_id
                        AND users.access_state = 'active'
                  )
                """,
                (
                    SlotStatus.MISSED.value,
                    now_text,
                    MissReason.USER_UNAVAILABLE.value,
                    SlotStatus.PLANNED.value,
                    now_text,
                ),
            )
            conn.execute(
                "UPDATE scheduled_check_slots "
                "SET status = ?, finished_at = ?, miss_reason = ? "
                "WHERE status = ? AND planned_at < ?",
                (
                    SlotStatus.MISSED.value,
                    now_text,
                    MissReason.GRACE_EXPIRED.value,
                    SlotStatus.PLANNED.value,
                    cutoff_text,
                ),
            )

            due_rows = conn.execute(
                """
                SELECT slots.*
                FROM scheduled_check_slots AS slots
                JOIN users ON users.user_id = slots.user_id
                WHERE slots.status = ?
                  AND slots.planned_at >= ?
                  AND slots.planned_at <= ?
                  AND users.access_state = 'active'
                ORDER BY slots.user_id, slots.planned_at DESC, slots.ordinal DESC
                """,
                (SlotStatus.PLANNED.value, cutoff_text, now_text),
            ).fetchall()

            newest_by_user: dict[int, sqlite3.Row] = {}
            for row in due_rows:
                user_id = int(row["user_id"])
                if user_id not in newest_by_user:
                    newest_by_user[user_id] = row
                    continue
                self._miss_planned_row(
                    conn, row, now_text, MissReason.SUPERSEDED_CATCH_UP
                )

            claimable: list[ScheduledCheckSlot] = []
            for row in newest_by_user.values():
                slot = self._row_to_slot(row)
                latest_started = conn.execute(
                    "SELECT MAX(started_at) FROM scheduled_check_slots "
                    "WHERE user_id = ? AND started_at IS NOT NULL",
                    (slot.user_id,),
                ).fetchone()[0]
                if latest_started is None:
                    claimable.append(slot)
                    continue

                earliest_start = datetime.fromisoformat(str(latest_started)) + minimum_spacing
                grace_deadline = slot.planned_at + grace
                if earliest_start > grace_deadline:
                    self._miss_planned_row(
                        conn, row, now_text, MissReason.SPACING_CONFLICT
                    )
                elif earliest_start <= now:
                    claimable.append(slot)

        return tuple(
            sorted(
                claimable,
                key=lambda slot: (slot.planned_at, slot.user_id, slot.ordinal),
            )
        )

    def claim(
        self,
        identity: SlotIdentity,
        now: datetime,
        grace: timedelta,
        minimum_spacing: timedelta,
    ) -> ScheduledCheckSlot | None:
        _positive_duration(grace, "grace")
        _positive_duration(minimum_spacing, "minimum_spacing")
        now_text = _utc_text(now)
        cutoff_text = _utc_text(now - grace)

        with self._immediate_transaction() as conn:
            row = conn.execute(
                """
                SELECT slots.*
                FROM scheduled_check_slots AS slots
                JOIN users ON users.user_id = slots.user_id
                WHERE slots.user_id = ?
                  AND slots.schedule_date = ?
                  AND slots.ordinal = ?
                  AND slots.status = ?
                  AND slots.planned_at >= ?
                  AND slots.planned_at <= ?
                  AND users.access_state = 'active'
                """,
                (
                    identity.user_id,
                    identity.schedule_date.isoformat(),
                    identity.ordinal,
                    SlotStatus.PLANNED.value,
                    cutoff_text,
                    now_text,
                ),
            ).fetchone()
            if row is None:
                return None

            newer_due = conn.execute(
                """
                SELECT 1 FROM scheduled_check_slots
                WHERE user_id = ?
                  AND status = ?
                  AND planned_at >= ?
                  AND planned_at <= ?
                  AND (
                      planned_at > ?
                      OR (planned_at = ? AND ordinal > ?)
                  )
                LIMIT 1
                """,
                (
                    identity.user_id,
                    SlotStatus.PLANNED.value,
                    cutoff_text,
                    now_text,
                    row["planned_at"],
                    row["planned_at"],
                    identity.ordinal,
                ),
            ).fetchone()
            if newer_due is not None:
                return None

            latest_started = conn.execute(
                "SELECT MAX(started_at) FROM scheduled_check_slots "
                "WHERE user_id = ? AND started_at IS NOT NULL",
                (identity.user_id,),
            ).fetchone()[0]
            if latest_started is not None:
                elapsed = now - datetime.fromisoformat(str(latest_started))
                if elapsed < minimum_spacing:
                    return None

            cursor = conn.execute(
                "UPDATE scheduled_check_slots "
                "SET status = ?, started_at = ?, finished_at = NULL, miss_reason = NULL "
                "WHERE user_id = ? AND schedule_date = ? AND ordinal = ? AND status = ?",
                (
                    SlotStatus.RUNNING.value,
                    now_text,
                    identity.user_id,
                    identity.schedule_date.isoformat(),
                    identity.ordinal,
                    SlotStatus.PLANNED.value,
                ),
            )
            if cursor.rowcount != 1:
                return None
            claimed = conn.execute(
                "SELECT * FROM scheduled_check_slots "
                "WHERE user_id = ? AND schedule_date = ? AND ordinal = ?",
                (
                    identity.user_id,
                    identity.schedule_date.isoformat(),
                    identity.ordinal,
                ),
            ).fetchone()
            assert claimed is not None
            return self._row_to_slot(claimed)

    def complete(self, identity: SlotIdentity, now: datetime) -> bool:
        with self._immediate_transaction() as conn:
            cursor = conn.execute(
                "UPDATE scheduled_check_slots "
                "SET status = ?, finished_at = ?, miss_reason = NULL "
                "WHERE user_id = ? AND schedule_date = ? AND ordinal = ? AND status = ? "
                "AND started_at <= ?",
                (
                    SlotStatus.COMPLETED.value,
                    _utc_text(now),
                    identity.user_id,
                    identity.schedule_date.isoformat(),
                    identity.ordinal,
                    SlotStatus.RUNNING.value,
                    _utc_text(now),
                ),
            )
            return cursor.rowcount == 1

    def miss(
        self,
        identity: SlotIdentity,
        now: datetime,
        reason: MissReason,
    ) -> bool:
        with self._immediate_transaction() as conn:
            cursor = conn.execute(
                "UPDATE scheduled_check_slots "
                "SET status = ?, finished_at = ?, miss_reason = ? "
                "WHERE user_id = ? AND schedule_date = ? AND ordinal = ? "
                "AND status IN (?, ?) AND planned_at <= ?",
                (
                    SlotStatus.MISSED.value,
                    _utc_text(now),
                    reason.value,
                    identity.user_id,
                    identity.schedule_date.isoformat(),
                    identity.ordinal,
                    SlotStatus.PLANNED.value,
                    SlotStatus.RUNNING.value,
                    _utc_text(now),
                ),
            )
            return cursor.rowcount == 1

    def next_planned_for_user(
        self, user_id: int, now: datetime
    ) -> ScheduledCheckSlot | None:
        row = self._store.conn.execute(
            """
            SELECT slots.*
            FROM scheduled_check_slots AS slots
            JOIN users ON users.user_id = slots.user_id
            WHERE slots.user_id = ?
              AND slots.status = ?
              AND slots.planned_at >= ?
              AND users.access_state = 'active'
            ORDER BY slots.planned_at, slots.ordinal
            LIMIT 1
            """,
            (user_id, SlotStatus.PLANNED.value, _utc_text(now)),
        ).fetchone()
        return self._row_to_slot(row) if row is not None else None

    def next_planned_at(self, now: datetime) -> datetime | None:
        row = self._store.conn.execute(
            """
            SELECT MIN(slots.planned_at)
            FROM scheduled_check_slots AS slots
            JOIN users ON users.user_id = slots.user_id
            WHERE slots.status = ?
              AND slots.planned_at >= ?
              AND users.access_state = 'active'
            """,
            (SlotStatus.PLANNED.value, _utc_text(now)),
        ).fetchone()
        return datetime.fromisoformat(str(row[0])) if row is not None and row[0] else None

    def prune_terminal(self, before: datetime) -> int:
        with self._immediate_transaction() as conn:
            cursor = conn.execute(
                "DELETE FROM scheduled_check_slots "
                "WHERE status IN (?, ?) AND finished_at < ?",
                (
                    SlotStatus.COMPLETED.value,
                    SlotStatus.MISSED.value,
                    _utc_text(before),
                ),
            )
            return cursor.rowcount

    @staticmethod
    def _miss_planned_row(
        conn: sqlite3.Connection,
        row: sqlite3.Row,
        now_text: str,
        reason: MissReason,
    ) -> None:
        conn.execute(
            "UPDATE scheduled_check_slots "
            "SET status = ?, finished_at = ?, miss_reason = ? "
            "WHERE user_id = ? AND schedule_date = ? AND ordinal = ? AND status = ?",
            (
                SlotStatus.MISSED.value,
                now_text,
                reason.value,
                row["user_id"],
                row["schedule_date"],
                row["ordinal"],
                SlotStatus.PLANNED.value,
            ),
        )

    @staticmethod
    def _row_to_slot(row: sqlite3.Row) -> ScheduledCheckSlot:
        miss_reason = row["miss_reason"]
        return ScheduledCheckSlot(
            identity=SlotIdentity(
                user_id=int(row["user_id"]),
                schedule_date=date.fromisoformat(str(row["schedule_date"])),
                ordinal=int(row["ordinal"]),
            ),
            planned_at=datetime.fromisoformat(str(row["planned_at"])),
            status=SlotStatus(str(row["status"])),
            started_at=(
                datetime.fromisoformat(str(row["started_at"]))
                if row["started_at"] is not None
                else None
            ),
            finished_at=(
                datetime.fromisoformat(str(row["finished_at"]))
                if row["finished_at"] is not None
                else None
            ),
            miss_reason=MissReason(str(miss_reason)) if miss_reason is not None else None,
        )
