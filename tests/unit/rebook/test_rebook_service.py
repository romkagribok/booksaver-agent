from __future__ import annotations

import uuid
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from booksaver.application.rebook_service import (
    RebookSessionService,
    SupersededOpportunityError,
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
    def __init__(self, *, current_at_insert: bool = True) -> None:
        self.sessions: dict[str, RebookSession] = {}
        self.current_at_insert = current_at_insert

    def add(self, session: RebookSession) -> None:
        self.sessions[session.session_id] = session

    def add_if_opportunity_current(self, session: RebookSession) -> bool:
        if not self.current_at_insert:
            return False
        self.add(session)
        return True

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

    def get_current_for_booking(self, booking_id: str) -> SavingsOpportunity | None:
        matches = self.list_for_booking(booking_id)
        indexed = list(enumerate(matches))
        latest = max(indexed, key=lambda item: (item[1].validated_at, item[0]), default=None)
        return latest[1] if latest is not None else None

    def list_for_booking(self, booking_id: str) -> list[SavingsOpportunity]:
        return [o for o in self._by_id.values() if o.booking_id == booking_id]

    def list_all(self) -> list[SavingsOpportunity]:
        return list(self._by_id.values())

    def list_all_for_user(self, user_id: int) -> list[SavingsOpportunity]:
        return list(self._by_id.values())

    def list_current_for_user(self, user_id: int) -> list[SavingsOpportunity]:
        latest_by_booking: dict[str, tuple[int, SavingsOpportunity]] = {}
        for index, opportunity in enumerate(self._by_id.values()):
            current = latest_by_booking.get(opportunity.booking_id)
            if current is None or (opportunity.validated_at, index) > (
                current[1].validated_at,
                current[0],
            ):
                latest_by_booking[opportunity.booking_id] = (index, opportunity)
        ordered = sorted(
            latest_by_booking.values(),
            key=lambda value: (value[1].validated_at, value[0]),
            reverse=True,
        )
        return [value[1] for value in ordered]

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


def test_superseded_opportunity_creates_no_session_or_prompt() -> None:
    older = _opportunity()
    newer = SavingsOpportunity(
        opportunity_id=str(uuid.uuid4()),
        booking_id=older.booking_id,
        check_id="chk-2",
        baseline_price=older.baseline_price,
        live_price=Money(amount=Decimal("340.00"), currency="EUR"),
        amount_saved=Money(amount=Decimal("60.00"), currency="EUR"),
        percent_saved=Decimal("15.00"),
        validated_at=older.validated_at + timedelta(minutes=1),
    )
    gate = ScriptedGate([True, True])
    sessions = FakeSessionRepo()
    events = FakeEventRepo()
    navigations: list[str] = []
    service = RebookSessionService(
        savings_repo=FakeSavingsRepo([older, newer]),
        booking_repo=FakeBookingRepository([make_booking("b-1")]),
        session_repo=sessions,
        event_repo=events,
        gate=gate,
        navigator=lambda url, desc: navigations.append(url),
    )

    with pytest.raises(SupersededOpportunityError, match="no longer current"):
        service.run(older.opportunity_id)

    assert sessions.sessions == {}
    assert gate.prompts == []
    assert events.events == []
    assert navigations == []


def test_fake_current_listing_uses_cross_booking_insertion_order_for_time_ties() -> None:
    at = datetime.now(UTC)
    first = replace(_opportunity("b-1"), validated_at=at)
    second = replace(_opportunity("b-2"), validated_at=at)

    assert [
        opportunity.booking_id
        for opportunity in FakeSavingsRepo([first, second]).list_current_for_user(1)
    ] == ["b-2", "b-1"]


def test_opportunity_superseded_at_atomic_insert_creates_no_partial_session() -> None:
    opportunity = _opportunity()
    gate = ScriptedGate([True, True])
    sessions = FakeSessionRepo(current_at_insert=False)
    events = FakeEventRepo()
    navigations: list[str] = []
    service = RebookSessionService(
        savings_repo=FakeSavingsRepo([opportunity]),
        booking_repo=FakeBookingRepository([make_booking("b-1")]),
        session_repo=sessions,
        event_repo=events,
        gate=gate,
        navigator=lambda url, desc: navigations.append(url),
    )

    with pytest.raises(SupersededOpportunityError, match="no longer current"):
        service.run(opportunity.opportunity_id)

    assert sessions.sessions == {}
    assert gate.prompts == []
    assert events.events == []
    assert navigations == []


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
