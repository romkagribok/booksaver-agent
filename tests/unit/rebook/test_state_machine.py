from __future__ import annotations

import pytest

from booksaver.domain.rebook import (
    ConfirmationAnswer,
    IllegalTransition,
    RebookSession,
    SessionState,
)


def _session() -> RebookSession:
    return RebookSession.start("opp-1", "b-1")


def _session_awaiting_cancel() -> RebookSession:
    s = _session()
    s.await_cancel_confirmation()
    return s


def _session_awaiting_book() -> RebookSession:
    s = _session_awaiting_cancel()
    s.approve()
    s.mark_cancel_executed()
    return s


# ── the happy path ────────────────────────────────────────────────────────────

def test_full_confirmed_flow() -> None:
    s = _session()
    assert s.state is SessionState.STARTED

    s.await_cancel_confirmation()
    s.approve()
    assert s.state is SessionState.CANCEL_APPROVED

    s.mark_cancel_executed()
    assert s.state is SessionState.AWAITING_BOOK_CONFIRMATION

    s.approve()
    assert s.state is SessionState.BOOK_APPROVED

    s.mark_book_executed()
    assert s.state is SessionState.COMPLETED
    assert s.is_terminal
    assert s.end_reason == "completed"


# ── US-011: destructive actions unreachable without confirmation ──────────────

def test_cancel_cannot_execute_from_started() -> None:
    with pytest.raises(IllegalTransition):
        _session().mark_cancel_executed()


def test_cancel_cannot_execute_while_awaiting_confirmation() -> None:
    with pytest.raises(IllegalTransition):
        _session_awaiting_cancel().mark_cancel_executed()


def test_book_cannot_execute_without_book_confirmation() -> None:
    # even after cancel was approved and executed, book needs its own approval
    s = _session_awaiting_book()
    with pytest.raises(IllegalTransition):
        s.mark_book_executed()


def test_book_cannot_execute_from_cancel_approved() -> None:
    s = _session_awaiting_cancel()
    s.approve()  # cancel approved — NOT book approval
    with pytest.raises(IllegalTransition):
        s.mark_book_executed()


def test_approval_is_single_use() -> None:
    # executing the cancel consumes the approval; a second cancel needs re-approval
    s = _session_awaiting_cancel()
    s.approve()
    s.mark_cancel_executed()
    with pytest.raises(IllegalTransition):
        s.mark_cancel_executed()


def test_approve_illegal_outside_awaiting_states() -> None:
    with pytest.raises(IllegalTransition):
        _session().approve()


# ── declines are safe and terminal ────────────────────────────────────────────

def test_decline_at_cancel_gate_is_terminal() -> None:
    s = _session_awaiting_cancel()
    s.decline()
    assert s.state is SessionState.DECLINED
    assert s.is_terminal
    assert s.end_reason == "declined"


def test_decline_at_book_gate_is_terminal() -> None:
    s = _session_awaiting_book()
    s.decline()
    assert s.state is SessionState.DECLINED


def test_no_action_possible_after_decline() -> None:
    s = _session_awaiting_cancel()
    s.decline()
    with pytest.raises(IllegalTransition):
        s.approve()
    with pytest.raises(IllegalTransition):
        s.mark_cancel_executed()
    with pytest.raises(IllegalTransition):
        s.mark_book_executed()


# ── error handling ────────────────────────────────────────────────────────────

def test_fail_from_any_non_terminal_state() -> None:
    s = _session_awaiting_book()
    s.fail("browser crashed")
    assert s.state is SessionState.ERROR
    assert s.is_terminal
    assert s.end_reason is not None and "browser crashed" in s.end_reason


def test_fail_from_terminal_state_is_illegal() -> None:
    s = _session_awaiting_cancel()
    s.decline()
    with pytest.raises(IllegalTransition):
        s.fail("too late")


def test_no_action_after_error() -> None:
    s = _session_awaiting_cancel()
    s.fail("boom")
    with pytest.raises(IllegalTransition):
        s.approve()


# ── ConfirmationAnswer: fail-safe parsing (US-011) ───────────────────────────

@pytest.mark.parametrize("text", ["yes", "y", "YES", "Yes", "  yes  ", "Y"])
def test_explicit_yes_approves(text: str) -> None:
    assert ConfirmationAnswer.from_input(text).approved is True


@pytest.mark.parametrize(
    "text",
    ["no", "n", "", "  ", "ok", "sure", "yeah", "yess", "yes!", "1", "true", "confirm"],
)
def test_anything_else_declines(text: str) -> None:
    assert ConfirmationAnswer.from_input(text).approved is False
