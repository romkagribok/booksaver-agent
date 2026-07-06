"""US-020/021/022: BookingComSearchMonitor with the agent, traces, and snapshots."""

from __future__ import annotations

from booksaver.domain.agent import (
    AgentAction,
    AgentActionType,
    AgentSettings,
    CheckTrace,
    ElementInfo,
    TraceKind,
)
from booksaver.domain.check_result import CheckOutcome, ExtractionMethod, FailureCode
from booksaver.monitor.failure_tracker import FailureTracker
from booksaver.monitor.search_check_job import BookingComSearchMonitor
from booksaver.monitor.session_manager import SessionManager
from booksaver.monitor.trace import SnapshotWriter

from .fakes import (
    FakeAgentBrain,
    FakeBookingRepository,
    FakeCheckHistoryRepository,
    FakeInteractiveBrowser,
    FakeSessionRepository,
    make_booking,
    make_session,
)

_PROPERTY_URL = (
    "https://www.booking.com/hotel/test.html"
    "?checkin=2026-09-01&checkout=2026-09-05&group_adults=2"
)

_ROOM_TABLE = "Standard Double\n€ 350.00\nFree cancellation"


class FakeCheckTraceRepository:
    def __init__(self) -> None:
        self.traces: list[CheckTrace] = []

    def add(self, trace: CheckTrace) -> None:
        self.traces.append(trace)

    def get(self, check_id: str) -> CheckTrace | None:
        return next((t for t in self.traces if t.check_id == check_id), None)


def _happy_browser() -> FakeInteractiveBrowser:
    browser = FakeInteractiveBrowser(titles=["Hotel Test"], page_text=_ROOM_TABLE)
    browser.property_url = _PROPERTY_URL
    browser.elements = (ElementInfo(ref="e0", role="button", label="Close popup"),)
    return browser


def _monitor(
    browser: FakeInteractiveBrowser,
    brain: FakeAgentBrain | None = None,
    trace_repo: FakeCheckTraceRepository | None = None,
    snapshot_writer: SnapshotWriter | None = None,
    settings: AgentSettings | None = None,
) -> BookingComSearchMonitor:
    history = FakeCheckHistoryRepository()
    return BookingComSearchMonitor(
        browser=browser,
        session_manager=SessionManager(FakeSessionRepository(make_session())),
        check_history=history,
        booking_repo=FakeBookingRepository([]),
        failure_tracker=FailureTracker(history),
        llm=None,
        brain=brain,
        agent_settings=settings,
        trace_repo=trace_repo,
        snapshot_writer=snapshot_writer,
    )


class TestAgentAssistedMarker:
    def test_agent_assisted_success_marked_agent(self):
        browser = _happy_browser()
        browser.fail_selectors = {"data-date"}

        def _fix(b: FakeInteractiveBrowser, action: AgentAction) -> None:
            b.fail_selectors.clear()

        browser.on_act = _fix
        brain = FakeAgentBrain([AgentAction(type=AgentActionType.CLICK, ref="e0")])
        monitor = _monitor(browser, brain=brain)
        result = monitor.run_check(make_booking())
        assert result.outcome is CheckOutcome.SUCCESS
        assert result.extraction_method is ExtractionMethod.AGENT

    def test_scripted_only_success_keeps_dom_method(self):
        monitor = _monitor(_happy_browser(), brain=FakeAgentBrain([]))
        result = monitor.run_check(make_booking())
        assert result.extraction_method is ExtractionMethod.DOM

    def test_without_brain_step_failures_stay_scripted_codes(self):
        browser = _happy_browser()
        browser.fail_selectors = {"data-date"}
        monitor = _monitor(browser, brain=None)
        result = monitor.run_check(make_booking())
        assert result.failure_reason.code is FailureCode.STEP_FAILED


class TestTracePersistence:
    def test_every_check_persists_a_trace(self):
        trace_repo = FakeCheckTraceRepository()
        monitor = _monitor(_happy_browser(), trace_repo=trace_repo)
        result = monitor.run_check(make_booking())
        [trace] = trace_repo.traces
        assert trace.check_id == result.check_id
        kinds = [e.kind for e in trace.events]
        assert kinds.count(TraceKind.JOURNEY_STEP) == 8  # all steps recorded
        assert kinds[-1] is TraceKind.CHECK_RESULT

    def test_escalation_events_appear_in_trace(self):
        browser = _happy_browser()
        browser.fail_selectors = {"data-date"}

        def _fix(b: FakeInteractiveBrowser, action: AgentAction) -> None:
            b.fail_selectors.clear()

        browser.on_act = _fix
        trace_repo = FakeCheckTraceRepository()
        monitor = _monitor(
            browser,
            brain=FakeAgentBrain([AgentAction(type=AgentActionType.CLICK, ref="e0")]),
            trace_repo=trace_repo,
        )
        monitor.run_check(make_booking())
        kinds = {e.kind for e in trace_repo.traces[0].events}
        assert TraceKind.ESCALATION_STARTED in kinds
        assert TraceKind.AGENT_ACTION in kinds
        assert TraceKind.AGENT_RESULT in kinds

    def test_occupancy_missing_check_still_traced(self):
        trace_repo = FakeCheckTraceRepository()
        monitor = _monitor(_happy_browser(), trace_repo=trace_repo)
        monitor.run_check(make_booking(occupancy=None))
        [trace] = trace_repo.traces
        assert "occupancy_missing" in trace.events[-1].detail


class TestFailureSnapshots:
    def test_failed_check_writes_snapshot(self, tmp_path):
        browser = _happy_browser()
        browser.titles = ["Wrong Hotel"]  # PROPERTY_NOT_FOUND
        writer = SnapshotWriter(tmp_path / "snapshots")
        monitor = _monitor(browser, snapshot_writer=writer)
        result = monitor.run_check(make_booking())
        assert result.outcome is CheckOutcome.FAILURE
        assert (tmp_path / "snapshots" / f"{result.check_id}.txt").exists()

    def test_successful_check_writes_no_snapshot(self, tmp_path):
        writer = SnapshotWriter(tmp_path / "snapshots")
        monitor = _monitor(_happy_browser(), snapshot_writer=writer)
        result = monitor.run_check(make_booking())
        assert result.outcome is CheckOutcome.SUCCESS
        assert not (tmp_path / "snapshots").exists()
