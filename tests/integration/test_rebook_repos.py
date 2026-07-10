from __future__ import annotations

from pathlib import Path

from booksaver.domain.rebook import EventType, RebookEvent, RebookSession, SessionState
from booksaver.infrastructure.persistence.sqlite_store import (
    SqliteRebookEventRepository,
    SqliteRebookSessionRepository,
    SqliteStore,
)

from .test_check_history import _register_booking


class TestSqliteRebookSessionRepository:
    def test_round_trip(self, tmp_path: Path) -> None:
        with SqliteStore(tmp_path / "t.db") as store:
            _register_booking(store)
            repo = SqliteRebookSessionRepository(store)
            session = RebookSession.start("opp-1", "b-1")
            repo.add(session)

            loaded = repo.get(session.session_id)

        assert loaded is not None
        assert loaded.opportunity_id == "opp-1"
        assert loaded.state is SessionState.STARTED
        assert loaded.ended_at is None

    def test_update_persists_state_transition(self, tmp_path: Path) -> None:
        with SqliteStore(tmp_path / "t.db") as store:
            _register_booking(store)
            repo = SqliteRebookSessionRepository(store)
            session = RebookSession.start("opp-1", "b-1")
            repo.add(session)

            session.await_cancel_confirmation()
            session.decline()
            repo.update(session)

            loaded = repo.get(session.session_id)

        assert loaded is not None
        assert loaded.state is SessionState.DECLINED
        assert loaded.ended_at is not None
        assert loaded.end_reason == "declined"

    def test_get_unknown_returns_none(self, tmp_path: Path) -> None:
        with SqliteStore(tmp_path / "t.db") as store:
            assert SqliteRebookSessionRepository(store).get("nope") is None


class TestSqliteRebookEventRepository:
    def test_append_only_trail_in_order(self, tmp_path: Path) -> None:
        with SqliteStore(tmp_path / "t.db") as store:
            repo = SqliteRebookEventRepository(store)
            repo.append(RebookEvent.record("s-1", EventType.STARTED, "begin"))
            repo.append(RebookEvent.record("s-1", EventType.CONFIRMATION_REQUESTED))
            repo.append(RebookEvent.record("s-1", EventType.DECLINED, "user said no"))
            repo.append(RebookEvent.record("s-2", EventType.STARTED))

            trail = repo.list_for_session("s-1")

        assert [e.event_type for e in trail] == [
            EventType.STARTED,
            EventType.CONFIRMATION_REQUESTED,
            EventType.DECLINED,
        ]
        assert trail[0].detail == "begin"
        assert trail[2].detail == "user said no"
