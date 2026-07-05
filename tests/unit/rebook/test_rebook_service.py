from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from booksaver.application.rebook_service import (
    RebookSessionService,
    UnknownOpportunityError,
)
from booksaver.domain.rebook import (
    ConfirmationAnswer,
    ConfirmationPrompt,
    EventType,
    RebookEvent,
    RebookSession,
    SessionState,
)
from booksaver.domain.savings import SavingsOpportunity
from booksaver.domain.value_objects import Money

from ..monitor.fakes import FakeBookingRepository, make_booking


class ScriptedGate:
    """ConfirmationGate fake answering from a script of booleans."""

    def __init__(self, answers: list[bool]) -> None:
        self._answers = list(answers)
        self.prompts: list[ConfirmationPrompt] = []

    def ask(self, prompt: ConfirmationPrompt) -> ConfirmationAnswer:
        self.prompts.append(prompt)
        return ConfirmationAnswer(approved=self._answers.pop(0), answered_at=datetime.now(UTC))


class FakeSessionRepo:
    def __init__(self) -> None:
        self.sessions: dict[str, RebookSession] = {}

    def add(self, session: RebookSession) -> None:
        self.sessions[session.session_id] = session

    def update(self, session: RebookSession) -> None:
        self.sessions[session.session_id] = session

    def get(self, session_id: str) -> RebookSession | None:
        return self.sessions.get(session_id)


class FakeEventRepo:
    def __init__(self) -> None:
        self.events: list[RebookEvent] = []

    def append(self, event: RebookEvent) -> None:
        self.events.append(event)

    def list_for_session(self, session_id: str) -> list[RebookEvent]:
        return [e for e in self.events if e.session_id == session_id]


class FakeSavingsRepo:
    def __init__(self, opportunities: list[SavingsOpportunity]) -> None:
        self._by_id = {o.opportunity_id: o for o in opportunities}

    def add(self, opportunity: SavingsOpportunity) -> None:
        self._by_id[opportunity.opportunity_id] = opportunity

    def get(self, opportunity_id: str) -> SavingsOpportunity | None:
        return self._by_id.get(opportunity_id)

    def list_for_booking(self, booking_id: str) -> list[SavingsOpportunity]:
        return [o for o in self._by_id.values() if o.booking_id == booking_id]

    def list_all(self) -> list[SavingsOpportunity]:
        return list(self._by_id.values())

    def mark_notified(self, opportunity_id: str, at: datetime) -> None:
        pass


def _opportunity(booking_id: str = "b-1") -> SavingsOpportunity:
    return SavingsOpportunity(
        opportunity_id=str(uuid.uuid4()),
        booking_id=booking_id,
        check_id="chk-1",
        baseline_price=Money(amount=Decimal("400.00"), currency="EUR"),
        live_price=Money(amount=Decimal("350.00"), currency="EUR"),
        amount_saved=Money(amount=Decimal("50.00"), currency="EUR"),
        percent_saved=Decimal("12.50"),
        validated_at=datetime.now(UTC),
    )


def _make_service(
    answers: list[bool],
    opportunity: SavingsOpportunity | None = None,
) -> tuple[RebookSessionService, ScriptedGate, FakeEventRepo, list[str], SavingsOpportunity]:
    opp = opportunity or _opportunity()
    gate = ScriptedGate(answers)
    events = FakeEventRepo()
    navigations: list[str] = []
    service = RebookSessionService(
        savings_repo=FakeSavingsRepo([opp]),
        booking_repo=FakeBookingRepository([make_booking("b-1")]),
        session_repo=FakeSessionRepo(),
        event_repo=events,
        gate=gate,
        navigator=lambda url, desc: navigations.append(url),
    )
    return service, gate, events, navigations, opp


def _event_types(events: FakeEventRepo) -> list[EventType]:
    return [e.event_type for e in events.events]


# ── US-010: explicit intent ───────────────────────────────────────────────────

def test_unknown_opportunity_creates_no_session() -> None:
    service, _, events, navigations, _ = _make_service([True, True])
    with pytest.raises(UnknownOpportunityError):
        service.run("nonexistent")
    assert events.events == []       # nothing logged
    assert navigations == []          # nothing navigated


# ── US-011: confirmation gates ────────────────────────────────────────────────

def test_decline_first_gate_no_navigation() -> None:
    service, gate, events, navigations, opp = _make_service([False])

    session = service.run(opp.opportunity_id)

    assert session.state is SessionState.DECLINED
    assert navigations == []          # no destructive step even prepared
    assert EventType.DECLINED in _event_types(events)
    assert EventType.ACTION_EXECUTED not in _event_types(events)


def test_decline_second_gate_stops_after_cancel() -> None:
    service, gate, events, navigations, opp = _make_service([True, False])

    session = service.run(opp.opportunity_id)

    assert session.state is SessionState.DECLINED
    assert len(navigations) == 1      # only the cancel page was opened
    types = _event_types(events)
    assert types.count(EventType.CONFIRMATION_REQUESTED) == 2
    assert types.count(EventType.CONFIRMED) == 1
    assert types.count(EventType.DECLINED) == 1


def test_full_confirmation_flow() -> None:
    service, gate, events, navigations, opp = _make_service([True, True])

    session = service.run(opp.opportunity_id)

    assert session.state is SessionState.COMPLETED
    assert len(navigations) == 2
    types = _event_types(events)
    assert types.count(EventType.CONFIRMATION_REQUESTED) == 2   # one per destructive step
    assert types.count(EventType.CONFIRMED) == 2
    assert types[-1] is EventType.COMPLETED


def test_each_gate_shows_old_vs_new_price() -> None:
    service, gate, _, _, opp = _make_service([True, True])
    service.run(opp.opportunity_id)

    assert len(gate.prompts) == 2
    for prompt in gate.prompts:
        assert prompt.old_price == Money(amount=Decimal("400.00"), currency="EUR")
        assert prompt.new_price == Money(amount=Decimal("350.00"), currency="EUR")
        assert prompt.refundability_summary   # non-empty


# ── US-012: audit trail ───────────────────────────────────────────────────────

def test_declined_session_audit_trail() -> None:
    service, _, events, _, opp = _make_service([False])
    session = service.run(opp.opportunity_id)

    trail = events.list_for_session(session.session_id)
    assert [e.event_type for e in trail] == [
        EventType.STARTED,
        EventType.CONFIRMATION_REQUESTED,
        EventType.DECLINED,
    ]


def test_completed_session_audit_trail() -> None:
    service, _, events, _, opp = _make_service([True, True])
    session = service.run(opp.opportunity_id)

    trail = events.list_for_session(session.session_id)
    assert [e.event_type for e in trail] == [
        EventType.STARTED,
        EventType.CONFIRMATION_REQUESTED,
        EventType.CONFIRMED,
        EventType.ACTION_EXECUTED,
        EventType.CONFIRMATION_REQUESTED,
        EventType.CONFIRMED,
        EventType.ACTION_EXECUTED,
        EventType.COMPLETED,
    ]


def test_navigator_failure_ends_session_with_error_event() -> None:
    opp = _opportunity()
    events = FakeEventRepo()

    def _explode(url: str, desc: str) -> None:
        raise RuntimeError("browser exploded")

    service = RebookSessionService(
        savings_repo=FakeSavingsRepo([opp]),
        booking_repo=FakeBookingRepository([make_booking("b-1")]),
        session_repo=FakeSessionRepo(),
        event_repo=events,
        gate=ScriptedGate([True]),
        navigator=_explode,
    )

    with pytest.raises(RuntimeError):
        service.run(opp.opportunity_id)

    types = _event_types(events)
    assert EventType.ERROR in types
    assert EventType.COMPLETED not in types
