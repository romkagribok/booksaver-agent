"""SQLite persistence for paired price comparisons (intent 026)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal

from booksaver.domain.price_comparison import (
    ArmResult,
    ArmStatus,
    ComparisonArm,
    ComparisonTrigger,
)

from .sqlite_store import SqliteStore

# A pending arm older than this belongs to an interrupted process; it is closed honestly as
# interrupted rather than replayed, so an unknown billable attempt is never repeated.
_INTERRUPTED_AFTER = timedelta(minutes=20)


def _amount(value: Decimal) -> str:
    """One canonical text form so agreement queries compare amounts, not formatting."""
    return str(value.quantize(Decimal("0.01")))


@dataclass(frozen=True, slots=True)
class ComparisonSummaryRow:
    arm: str
    status: str
    count: int
    cost_nano_usd: int
    unknown_cost_count: int
    conservative_cost_count: int
    average_seconds: float | None


class SqlitePriceComparisonRepository:
    def __init__(self, store: SqliteStore) -> None:
        self._store = store

    def begin(
        self,
        *,
        comparison_id: str,
        user_id: int,
        booking_id: str,
        trigger: ComparisonTrigger,
        cohort: str,
        first_arm: ComparisonArm,
        now: datetime,
    ) -> None:
        """Persist the pair and both pending arms before any browser or provider work."""

        conn = self._store.conn
        conn.execute(
            "UPDATE price_comparison_arms SET status = 'failure', outcome_code = 'interrupted', "
            "finished_at = ?, detail = 'The process stopped before this method finished.' "
            "WHERE status = 'pending' AND comparison_id IN "
            "(SELECT comparison_id FROM price_comparisons WHERE created_at < ?)",
            (now.isoformat(), (now - _INTERRUPTED_AFTER).isoformat()),
        )
        conn.execute(
            "INSERT INTO price_comparisons "
            "(comparison_id, user_id, booking_id, trigger, cohort, first_arm, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                comparison_id,
                user_id,
                booking_id,
                trigger.value,
                cohort,
                first_arm.value,
                now.isoformat(),
            ),
        )
        for arm in ComparisonArm:
            conn.execute(
                "INSERT INTO price_comparison_arms (comparison_id, arm, status) "
                "VALUES (?, ?, 'pending')",
                (comparison_id, arm.value),
            )
        conn.commit()

    def record_arm(self, comparison_id: str, result: ArmResult) -> None:
        self._store.conn.execute(
            "UPDATE price_comparison_arms SET status = ?, outcome_code = ?, live_amount = ?, "
            "live_currency = ?, room_label = ?, savings_amount = ?, model_calls = ?, "
            "input_tokens = ?, output_tokens = ?, cost_nano_usd = ?, cost_certainty = ?, "
            "started_at = ?, finished_at = ?, detail = ? "
            "WHERE comparison_id = ? AND arm = ? AND status = 'pending'",
            (
                result.status.value,
                result.outcome_code,
                _amount(result.live_price.amount) if result.live_price is not None else None,
                result.live_price.currency if result.live_price is not None else None,
                result.room_label,
                _amount(result.savings.amount) if result.savings is not None else None,
                result.model_calls,
                result.input_tokens,
                result.output_tokens,
                result.cost_nano_usd,
                result.cost_certainty.value,
                result.started_at.isoformat(),
                result.finished_at.isoformat(),
                result.detail[:300],
                comparison_id,
                result.arm.value,
            ),
        )
        self._store.conn.commit()

    def mark_report(self, comparison_id: str, status: str, now: datetime) -> None:
        if status not in {"sent", "failed", "suppressed"}:
            raise ValueError("unsupported report status")
        self._store.conn.execute(
            "UPDATE price_comparisons SET report_status = ?, report_at = ? "
            "WHERE comparison_id = ?",
            (status, now.isoformat(), comparison_id),
        )
        self._store.conn.commit()

    def jev_cost_since(self, since: datetime) -> int:
        """Charged Jev nano-USD since ``since`` (unknown-cost arms are not counted here)."""

        row = self._store.conn.execute(
            "SELECT COALESCE(SUM(a.cost_nano_usd), 0) FROM price_comparison_arms a "
            "JOIN price_comparisons c ON c.comparison_id = a.comparison_id "
            "WHERE a.arm = 'jev' AND c.created_at >= ?",
            (since.isoformat(),),
        ).fetchone()
        return int(row[0])

    def summary(self, since: datetime) -> tuple[ComparisonSummaryRow, ...]:
        rows = self._store.conn.execute(
            "SELECT a.arm, a.status, COUNT(*), COALESCE(SUM(a.cost_nano_usd), 0), "
            "SUM(CASE WHEN a.cost_nano_usd IS NULL THEN 1 ELSE 0 END), "
            "SUM(CASE WHEN a.cost_certainty = 'conservative' THEN 1 ELSE 0 END), "
            "AVG((julianday(a.finished_at) - julianday(a.started_at)) * 86400.0) "
            "FROM price_comparison_arms a "
            "JOIN price_comparisons c ON c.comparison_id = a.comparison_id "
            "WHERE c.created_at >= ? GROUP BY a.arm, a.status ORDER BY a.arm, a.status",
            (since.isoformat(),),
        ).fetchall()
        return tuple(
            ComparisonSummaryRow(
                arm=str(row[0]),
                status=str(row[1]),
                count=int(row[2]),
                cost_nano_usd=int(row[3]),
                unknown_cost_count=int(row[4] or 0),
                conservative_cost_count=int(row[5] or 0),
                average_seconds=float(row[6]) if row[6] is not None else None,
            )
            for row in rows
        )

    def agreement_counts(self, since: datetime) -> tuple[int, int]:
        """Pairs where both arms succeeded, and how many of those reported the same price."""

        row = self._store.conn.execute(
            "SELECT COUNT(*), SUM(CASE WHEN b.live_amount = j.live_amount "
            "AND b.live_currency = j.live_currency THEN 1 ELSE 0 END) "
            "FROM price_comparisons c "
            "JOIN price_comparison_arms b ON b.comparison_id = c.comparison_id "
            "AND b.arm = 'baseline' AND b.status = ? "
            "JOIN price_comparison_arms j ON j.comparison_id = c.comparison_id "
            "AND j.arm = 'jev' AND j.status = ? "
            "WHERE c.created_at >= ?",
            (ArmStatus.SUCCESS.value, ArmStatus.SUCCESS.value, since.isoformat()),
        ).fetchone()
        return int(row[0] or 0), int(row[1] or 0)
