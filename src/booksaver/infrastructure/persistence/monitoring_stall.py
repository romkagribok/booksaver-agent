"""Durable stall notices and the facts needed to evaluate them, scoped to one user."""

from __future__ import annotations

import json
from collections.abc import Sequence
from datetime import date, datetime

from booksaver.domain.account_sync import EligibilityReason, EligibilityStatus
from booksaver.domain.check_result import CheckOutcome, FailureCode
from booksaver.domain.monitoring_stall import MonitoredReservation, StallReason
from booksaver.infrastructure.persistence.sqlite_store import SqliteStore


def _sync_blocks_checks(sync: Sequence[object] | None, observed_in_run: object) -> bool:
    """Whether the latest sync stops this reservation's check, as the scheduled run decides it."""
    if sync is None or sync[1] == "complete":
        return False
    if sync[1] != "incomplete":
        return True
    # An incomplete agentic sync still checks what it positively observed; other syncs do not.
    return not sync[2] or observed_in_run != sync[0]


class SqliteMonitoringStallRepository:
    def __init__(self, store: SqliteStore) -> None:
        self._conn = store.conn

    def list_upcoming(self, user_id: int, today: date) -> tuple[MonitoredReservation, ...]:
        sync = self._conn.execute(
            "SELECT s.run_id, s.completeness, "
            "EXISTS (SELECT 1 FROM agentic_inventory_executions e "
            "WHERE e.run_id = s.run_id AND e.user_id = s.user_id) "
            "FROM booking_sync_runs s WHERE s.user_id = ? "
            "ORDER BY s.started_at DESC LIMIT 1",
            (user_id,),
        ).fetchone()
        rows = self._conn.execute(
            """
            SELECT r.account_reservation_id, r.property_name, r.eligibility_status,
                   r.eligibility_reasons, r.first_observed_at, r.last_sync_run_id,
                   (SELECT MAX(h.checked_at) FROM check_history h
                     WHERE h.booking_id = r.monitoring_booking_id
                       AND (h.outcome = ? OR h.failure_code = ?)) AS last_conclusive
            FROM account_reservations r
            WHERE r.user_id = ? AND r.remote_lifecycle = 'upcoming' AND r.check_out > ?
            """,
            (
                CheckOutcome.SUCCESS.value,
                FailureCode.NO_EQUIVALENT_OFFER.value,
                user_id,
                today.isoformat(),
            ),
        ).fetchall()
        return tuple(
            MonitoredReservation(
                reservation_key=row[0],
                property_name=row[1] or "Your reservation",
                eligibility=EligibilityStatus(row[2]),
                eligibility_reasons=frozenset(
                    EligibilityReason(value) for value in json.loads(row[3] or "[]")
                ),
                first_observed_at=datetime.fromisoformat(row[4]),
                last_conclusive_at=datetime.fromisoformat(row[6]) if row[6] else None,
                latest_sync_failed=_sync_blocks_checks(sync, row[5]),
            )
            for row in rows
        )

    def notices(self, user_id: int) -> dict[str, datetime]:
        rows = self._conn.execute(
            "SELECT booking_id, notified_at FROM monitoring_stall_notices WHERE user_id = ?",
            (user_id,),
        ).fetchall()
        return {row[0]: datetime.fromisoformat(row[1]) for row in rows}

    def record(self, user_id: int, booking_id: str, reason: StallReason, at: datetime) -> None:
        self._conn.execute(
            "INSERT OR REPLACE INTO monitoring_stall_notices "
            "(booking_id, user_id, reason, notified_at) VALUES (?, ?, ?, ?)",
            (booking_id, user_id, reason.value, at.isoformat()),
        )
        self._conn.commit()

    def delete(self, user_id: int, booking_id: str) -> None:
        self._conn.execute(
            "DELETE FROM monitoring_stall_notices WHERE user_id = ? AND booking_id = ?",
            (user_id, booking_id),
        )
        self._conn.commit()
