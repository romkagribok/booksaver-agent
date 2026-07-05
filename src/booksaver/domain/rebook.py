from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum

from .errors import BookSaverError
from .value_objects import Money


class SessionState(Enum):
    STARTED = "started"
    AWAITING_CANCEL_CONFIRMATION = "awaiting_cancel_confirmation"
    CANCEL_APPROVED = "cancel_approved"
    AWAITING_BOOK_CONFIRMATION = "awaiting_book_confirmation"
    BOOK_APPROVED = "book_approved"
    COMPLETED = "completed"
    DECLINED = "declined"
    ERROR = "error"


_TERMINAL_STATES = {SessionState.COMPLETED, SessionState.DECLINED, SessionState.ERROR}


class EventType(Enum):
    STARTED = "started"
    CONFIRMATION_REQUESTED = "confirmation_requested"
    CONFIRMED = "confirmed"
    DECLINED = "declined"
    ACTION_EXECUTED = "action_executed"
    COMPLETED = "completed"
    ERROR = "error"


class RebookAction(Enum):
    CANCEL_EXISTING = "cancel_existing"
    BOOK_NEW = "book_new"


class IllegalTransition(BookSaverError):
    def __init__(self, current: SessionState, attempted: str) -> None:
        self.current = current
        self.attempted = attempted
        super().__init__(
            f"Illegal rebook transition: cannot {attempted} from state '{current.value}'"
        )


@dataclass(frozen=True)
class ConfirmationPrompt:
    action: RebookAction
    old_price: Money
    new_price: Money
    refundability_summary: str


@dataclass(frozen=True)
class ConfirmationAnswer:
    approved: bool
    answered_at: datetime

    @classmethod
    def from_input(cls, text: str, answered_at: datetime | None = None) -> ConfirmationAnswer:
        # Fail-safe default: only an explicit yes approves; anything else declines.
        normalised = text.strip().lower()
        return cls(
            approved=normalised in ("yes", "y"),
            answered_at=answered_at or datetime.now(UTC),
        )


@dataclass(frozen=True)
class RebookEvent:
    event_id: str
    session_id: str
    event_type: EventType
    detail: str
    occurred_at: datetime

    @classmethod
    def record(cls, session_id: str, event_type: EventType, detail: str = "") -> RebookEvent:
        return cls(
            event_id=str(uuid.uuid4()),
            session_id=session_id,
            event_type=event_type,
            detail=detail,
            occurred_at=datetime.now(UTC),
        )


@dataclass
class RebookSession:
    """The rebook state machine (US-010/011).

    Destructive actions are structurally unreachable without confirmation: the
    only route to CANCEL_APPROVED / BOOK_APPROVED is approve() from the matching
    awaiting state, and executing the action immediately leaves the approved
    state, so each destructive step needs a fresh confirmation cycle.
    """

    session_id: str
    opportunity_id: str
    booking_id: str
    state: SessionState
    started_at: datetime
    ended_at: datetime | None = None
    end_reason: str | None = None
    _history: list[SessionState] = field(default_factory=list, repr=False)

    @classmethod
    def start(cls, opportunity_id: str, booking_id: str) -> RebookSession:
        return cls(
            session_id=str(uuid.uuid4()),
            opportunity_id=opportunity_id,
            booking_id=booking_id,
            state=SessionState.STARTED,
            started_at=datetime.now(UTC),
        )

    def _transition(self, allowed_from: SessionState, to: SessionState, action: str) -> None:
        if self.state is not allowed_from:
            raise IllegalTransition(self.state, action)
        self._history.append(self.state)
        self.state = to

    def await_cancel_confirmation(self) -> None:
        self._transition(
            SessionState.STARTED,
            SessionState.AWAITING_CANCEL_CONFIRMATION,
            "await cancel confirmation",
        )

    def approve(self) -> None:
        if self.state is SessionState.AWAITING_CANCEL_CONFIRMATION:
            self._history.append(self.state)
            self.state = SessionState.CANCEL_APPROVED
        elif self.state is SessionState.AWAITING_BOOK_CONFIRMATION:
            self._history.append(self.state)
            self.state = SessionState.BOOK_APPROVED
        else:
            raise IllegalTransition(self.state, "approve")

    def decline(self) -> None:
        if self.state not in (
            SessionState.AWAITING_CANCEL_CONFIRMATION,
            SessionState.AWAITING_BOOK_CONFIRMATION,
        ):
            raise IllegalTransition(self.state, "decline")
        self._history.append(self.state)
        self.state = SessionState.DECLINED
        self._end("declined")

    def mark_cancel_executed(self) -> None:
        self._transition(
            SessionState.CANCEL_APPROVED,
            SessionState.AWAITING_BOOK_CONFIRMATION,
            "execute cancel",
        )

    def mark_book_executed(self) -> None:
        self._transition(SessionState.BOOK_APPROVED, SessionState.COMPLETED, "execute book")
        self._end("completed")

    def fail(self, detail: str) -> None:
        if self.state in _TERMINAL_STATES:
            raise IllegalTransition(self.state, "fail")
        self._history.append(self.state)
        self.state = SessionState.ERROR
        self._end(f"error: {detail}")

    def _end(self, reason: str) -> None:
        self.ended_at = datetime.now(UTC)
        self.end_reason = reason

    @property
    def is_terminal(self) -> bool:
        return self.state in _TERMINAL_STATES
