from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from booksaver.domain.check_result import CheckResult, FailureCode, FailureReason
from booksaver.domain.session import SessionState, SessionStatus
from booksaver.domain.value_objects import Platform
from booksaver.monitor.failure_tracker import FailureTracker
from booksaver.monitor.session_manager import SessionManager

from .fakes import FakeCheckHistoryRepository, FakeSessionRepository, make_session

# ── SessionManager ────────────────────────────────────────────────────────────

def test_ensure_active_returns_session_when_valid() -> None:
    session = make_session()
    manager = SessionManager(FakeSessionRepository(session))
    assert manager.ensure_active() is session


def test_ensure_active_returns_none_when_no_session() -> None:
    manager = SessionManager(FakeSessionRepository(None))
    assert manager.ensure_active() is None


def test_ensure_active_returns_none_for_reauth_required() -> None:
    session = make_session().with_status(SessionStatus.REQUIRES_REAUTH)
    manager = SessionManager(FakeSessionRepository(session))
    assert manager.ensure_active() is None


def test_ensure_active_expires_session_past_expiry() -> None:
    session = SessionState.new(
        platform=Platform.BOOKING_COM,
        cookies=b"[]",
        authenticated_at=datetime.now(UTC) - timedelta(days=30),
        expires_at=datetime.now(UTC) - timedelta(days=1),
    )
    repo = FakeSessionRepository(session)
    manager = SessionManager(repo)

    assert manager.ensure_active() is None
    assert repo.session is not None
    assert repo.session.status is SessionStatus.EXPIRED  # transition persisted


def test_mark_reauth_required_persists_status() -> None:
    session = make_session()
    repo = FakeSessionRepository(session)
    manager = SessionManager(repo)

    manager.mark_reauth_required(session)

    assert repo.session is not None
    assert repo.session.status is SessionStatus.REQUIRES_REAUTH


def test_save_refreshed_updates_cookies() -> None:
    session = make_session(cookies=b"old")
    repo = FakeSessionRepository(session)
    manager = SessionManager(repo)

    manager.save_refreshed(session, b"new-cookies")

    assert repo.session is not None
    assert repo.session.cookies == b"new-cookies"


# ── SessionState ──────────────────────────────────────────────────────────────

def test_session_without_expiry_never_expires() -> None:
    assert make_session().is_expired() is False


def test_session_with_future_expiry_not_expired() -> None:
    session = SessionState.new(
        platform=Platform.BOOKING_COM,
        cookies=b"[]",
        authenticated_at=datetime.now(UTC),
        expires_at=datetime.now(UTC) + timedelta(days=7),
    )
    assert session.is_expired() is False


# ── FailureTracker ────────────────────────────────────────────────────────────

def _failure(booking_id: str) -> CheckResult:
    return CheckResult.failure(
        booking_id,
        datetime.now(UTC),
        FailureReason(code=FailureCode.NAVIGATION_ERROR, detail="test"),
    )


def test_warning_emitted_at_threshold() -> None:
    history = FakeCheckHistoryRepository()
    tracker = FailureTracker(history, threshold=3)

    for i in range(3):
        history.add(_failure("b-1"))
        warned = tracker.after_check("b-1", succeeded=False)

    assert warned is True  # third consecutive failure hits the threshold


def test_no_warning_below_threshold() -> None:
    history = FakeCheckHistoryRepository()
    tracker = FailureTracker(history, threshold=3)

    history.add(_failure("b-1"))
    assert tracker.after_check("b-1", succeeded=False) is False
    history.add(_failure("b-1"))
    assert tracker.after_check("b-1", succeeded=False) is False


def test_warning_emitted_only_once_per_streak() -> None:
    history = FakeCheckHistoryRepository()
    tracker = FailureTracker(history, threshold=2)

    history.add(_failure("b-1"))
    tracker.after_check("b-1", succeeded=False)
    history.add(_failure("b-1"))
    assert tracker.after_check("b-1", succeeded=False) is True   # threshold hit
    history.add(_failure("b-1"))
    assert tracker.after_check("b-1", succeeded=False) is False  # already warned


def test_success_resets_warning_state() -> None:
    history = FakeCheckHistoryRepository()
    tracker = FailureTracker(history, threshold=2)

    history.add(_failure("b-1"))
    tracker.after_check("b-1", succeeded=False)
    history.add(_failure("b-1"))
    assert tracker.after_check("b-1", succeeded=False) is True

    tracker.after_check("b-1", succeeded=True)  # success resets the streak

    history.add(_failure("b-1"))
    history.add(_failure("b-1"))
    # count_consecutive_failures only sees trailing failures, but the fake's
    # history still has the old ones; what matters is the tracker warns again
    assert tracker.after_check("b-1", succeeded=False) is True


def test_invalid_threshold_rejected() -> None:
    with pytest.raises(ValueError, match="threshold must be >= 1"):
        FailureTracker(FakeCheckHistoryRepository(), threshold=0)
