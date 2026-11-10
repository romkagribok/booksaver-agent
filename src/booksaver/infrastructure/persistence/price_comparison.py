"""SQLite persistence for Jev price runs and the historical paired-comparison spend (intent 026)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from booksaver.domain.price_comparison import JevUsage

from .sqlite_store import SqliteStore


class SqlitePriceComparisonRepository:
    def __init__(self, store: SqliteStore) -> None:
        self._store = store

    def jev_cost_since(self, since: datetime, user_id: int) -> int:
        """One user's charged Jev nano-USD since ``since`` (unknown-cost arms are not counted)."""

        row = self._store.conn.execute(
            "SELECT COALESCE(SUM(a.cost_nano_usd), 0) FROM price_comparison_arms a "
            "JOIN price_comparisons c ON c.comparison_id = a.comparison_id "
            "WHERE a.arm = 'jev' AND c.created_at >= ? AND c.user_id = ?",
            (since.isoformat(), user_id),
        ).fetchone()
        return int(row[0])


@dataclass(frozen=True, slots=True)
class JevPriceRun:
    execution_id: str
    user_id: int
    booking_id: str
    created_at: datetime
    status: str
    usage: JevUsage
    latency_ms: int
    adapter: str
    diagnostic: str = ""


class SqliteJevPriceRunRepository:
    """Spend, daily-cap, and diagnostic record for Jev as the authoritative price method."""

    def __init__(self, store: SqliteStore) -> None:
        self._store = store

    def record(self, run: JevPriceRun) -> None:
        self._store.conn.execute(
            "INSERT OR REPLACE INTO jev_price_runs (execution_id, user_id, booking_id, "
            "created_at, status, model_calls, input_tokens, output_tokens, cost_nano_usd, "
            "cost_certainty, latency_ms, adapter, diagnostic) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                run.execution_id,
                run.user_id,
                run.booking_id,
                run.created_at.isoformat(),
                run.status,
                run.usage.calls,
                run.usage.input_tokens,
                run.usage.output_tokens,
                run.usage.cost_nano_usd,
                run.usage.certainty.value,
                max(0, run.latency_ms),
                run.adapter,
                run.diagnostic[:800],
            ),
        )
        self._store.conn.commit()

    def cost_since(self, since: datetime, user_id: int) -> int:
        """One user's Jev nano-USD since ``since``: the daily cap is per user."""
        row = self._store.conn.execute(
            "SELECT COALESCE(SUM(cost_nano_usd), 0) FROM jev_price_runs "
            "WHERE created_at >= ? AND user_id = ?",
            (since.isoformat(), user_id),
        ).fetchone()
        return int(row[0])

    def summary(self, since: datetime) -> tuple[tuple[str, int, int, float | None], ...]:
        """(status, runs, cost_nano_usd, average seconds) newest cohort first."""

        rows = self._store.conn.execute(
            "SELECT status, COUNT(*), COALESCE(SUM(cost_nano_usd), 0), AVG(latency_ms) / 1000.0 "
            "FROM jev_price_runs WHERE created_at >= ? GROUP BY status ORDER BY COUNT(*) DESC",
            (since.isoformat(),),
        ).fetchall()
        return tuple(
            (str(row[0]), int(row[1]), int(row[2]), float(row[3]) if row[3] is not None else None)
            for row in rows
        )

    def unobserved(
        self, since: datetime, *, limit: int = 20
    ) -> tuple[tuple[str, str, str, int, float, str], ...]:
        rows = self._store.conn.execute(
            "SELECT created_at, execution_id, status, model_calls, latency_ms / 1000.0, "
            "diagnostic FROM jev_price_runs WHERE status != 'observed' AND created_at >= ? "
            "ORDER BY created_at DESC LIMIT ?",
            (since.isoformat(), limit),
        ).fetchall()
        return tuple(
            (str(r[0]), str(r[1]), str(r[2]), int(r[3]), float(r[4]), str(r[5])) for r in rows
        )
