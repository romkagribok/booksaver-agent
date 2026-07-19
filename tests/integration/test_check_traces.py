"""US-022: check_traces persistence (schema v6) round trip."""

from datetime import UTC, datetime

from booksaver.domain.agent import CheckTrace, TraceEvent, TraceKind
from booksaver.infrastructure.persistence.sqlite_store import (
    SCHEMA_VERSION,
    SqliteCheckTraceRepository,
    SqliteStore,
)


def _trace(check_id: str = "chk-1") -> CheckTrace:
    now = datetime.now(UTC)
    return CheckTrace(
        check_id=check_id,
        booking_id="b-1",
        created_at=now,
        events=(
            TraceEvent(seq=0, at=now, kind=TraceKind.JOURNEY_STEP, detail="open_home: ok"),
            TraceEvent(
                seq=1, at=now, kind=TraceKind.ESCALATION_STARTED,
                detail="fill_search: selector missing",
            ),
            TraceEvent(
                seq=2, at=now, kind=TraceKind.CHECK_RESULT,
                detail="success: 350.00 EUR via agent",
            ),
        ),
    )


class TestCheckTraceRepository:
    def test_round_trip(self, tmp_path):
        with SqliteStore(tmp_path / "t.db") as store:
            repo = SqliteCheckTraceRepository(store)
            repo.add(_trace())
            loaded = repo.get("chk-1")

        assert loaded is not None
        assert loaded.check_id == "chk-1"
        assert loaded.booking_id == "b-1"
        assert len(loaded.events) == 3
        assert loaded.events[1].kind is TraceKind.ESCALATION_STARTED
        assert loaded.events[2].detail == "success: 350.00 EUR via agent"

    def test_missing_trace_returns_none(self, tmp_path):
        with SqliteStore(tmp_path / "t.db") as store:
            assert SqliteCheckTraceRepository(store).get("nope") is None

    def test_fresh_db_is_latest_schema(self, tmp_path):
        with SqliteStore(tmp_path / "t.db") as store:
            row = store.conn.execute("SELECT MAX(version) FROM schema_meta").fetchone()
        assert row[0] == SCHEMA_VERSION == 9
