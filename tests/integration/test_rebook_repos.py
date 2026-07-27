from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

from booksaver.domain.check_result import FailureCode
from booksaver.domain.rebook import EventType, RebookEvent, RebookSession, SessionState
from booksaver.infrastructure.persistence.sqlite_store import (
    SqliteRebookEventRepository,
    SqliteRebookSessionRepository,
    SqliteSavingsRepository,
    SqliteStore,
)

from .test_check_history import _register_booking
from .test_savings_repo import (
    _add_checked_opportunity,
    _opportunity,
    _record_failure,
)


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

    def test_atomic_add_rejects_opportunity_superseded_before_insert(
        self, tmp_path: Path
    ) -> None:
        now = datetime.now(UTC)
        with SqliteStore(tmp_path / "t.db") as store:
            _register_booking(store)
            savings = SqliteSavingsRepository(store)
            old = replace(
                _opportunity(),
                opportunity_id="old",
                validated_at=now,
            )
            newer = replace(
                _opportunity(),
                opportunity_id="newer",
                validated_at=now + timedelta(minutes=1),
            )
            _add_checked_opportunity(store, savings, old)
            _add_checked_opportunity(store, savings, newer)
            sessions = SqliteRebookSessionRepository(store)
            stale_session = RebookSession.start(old.opportunity_id, old.booking_id)
            current_session = RebookSession.start(newer.opportunity_id, newer.booking_id)

            assert sessions.add_if_opportunity_current(stale_session) is False
            assert sessions.get(stale_session.session_id) is None
            assert sessions.add_if_opportunity_current(current_session) is True
            assert sessions.get(current_session.session_id) is not None

    def test_atomic_add_preserves_current_opportunity_after_technical_failure(
        self, tmp_path: Path
    ) -> None:
        now = datetime.now(UTC)
        with SqliteStore(tmp_path / "t.db") as store:
            _register_booking(store)
            savings = SqliteSavingsRepository(store)
            opportunity = replace(
                _opportunity(),
                opportunity_id="last-verified",
                check_id="positive",
                validated_at=now,
            )
            _add_checked_opportunity(store, savings, opportunity)
            _record_failure(
                store,
                booking_id=opportunity.booking_id,
                check_id="timeout",
                checked_at=now + timedelta(minutes=1),
                code=FailureCode.TIMEOUT,
            )
            sessions = SqliteRebookSessionRepository(store)
            session = RebookSession.start(
                opportunity.opportunity_id, opportunity.booking_id
            )

            assert sessions.add_if_opportunity_current(session) is True
            assert sessions.get(session.session_id) is not None

    def test_atomic_add_rejects_opportunity_after_conclusive_invalidation(
        self, tmp_path: Path
    ) -> None:
        now = datetime.now(UTC)
        with SqliteStore(tmp_path / "t.db") as store:
            _register_booking(store)
            savings = SqliteSavingsRepository(store)
            opportunity = replace(
                _opportunity(),
                opportunity_id="invalidated",
                check_id="positive",
                validated_at=now,
            )
            _add_checked_opportunity(store, savings, opportunity)
            _record_failure(
                store,
                booking_id=opportunity.booking_id,
                check_id="no-equivalent",
                checked_at=now + timedelta(minutes=1),
                code=FailureCode.NO_EQUIVALENT_OFFER,
            )
            sessions = SqliteRebookSessionRepository(store)
            session = RebookSession.start(
                opportunity.opportunity_id, opportunity.booking_id
            )

            assert sessions.add_if_opportunity_current(session) is False
            assert sessions.get(session.session_id) is None


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
