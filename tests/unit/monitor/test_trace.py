from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from booksaver.domain.agent import AgentAction, AgentActionType, TraceKind
from booksaver.domain.check_result import (
    CheckResult,
    ExtractionMethod,
    FailureCode,
    FailureReason,
)
from booksaver.domain.journey import JourneyStep, StepOutcome
from booksaver.domain.value_objects import Money
from booksaver.monitor.trace import SnapshotWriter, TraceRecorder, redact


def _success_result() -> CheckResult:
    return CheckResult.success(
        booking_id="b-1",
        checked_at=datetime.now(UTC),
        live_price=Money(amount=Decimal("350.00"), currency="EUR"),
        extraction_method=ExtractionMethod.AGENT,
    )


def _failure_result() -> CheckResult:
    return CheckResult.failure(
        "b-1",
        datetime.now(UTC),
        FailureReason(code=FailureCode.AGENT_GAVE_UP, detail="stuck"),
    )


class TestTraceRecorder:
    def test_events_ordered_and_typed(self):
        recorder = TraceRecorder("b-1")
        recorder.journey_step(StepOutcome.success(JourneyStep.OPEN_HOME, "ok"))
        recorder.escalation_started(JourneyStep.FILL_SEARCH, "selector missing")
        recorder.agent_action(
            JourneyStep.FILL_SEARCH,
            AgentAction(type=AgentActionType.CLICK, ref="e0"),
            tier2=False,
        )
        recorder.agent_result(JourneyStep.FILL_SEARCH, "step completed by agent")
        result = _success_result()
        trace = recorder.finish(result)

        assert [e.seq for e in trace.events] == [0, 1, 2, 3, 4]
        assert [e.kind for e in trace.events] == [
            TraceKind.JOURNEY_STEP,
            TraceKind.ESCALATION_STARTED,
            TraceKind.AGENT_ACTION,
            TraceKind.AGENT_RESULT,
            TraceKind.CHECK_RESULT,
        ]
        assert trace.check_id == result.check_id
        assert trace.booking_id == "b-1"
        assert "350.00 EUR via agent" in trace.events[-1].detail

    def test_failure_result_recorded_with_code(self):
        recorder = TraceRecorder("b-1")
        trace = recorder.finish(_failure_result())
        assert "agent_gave_up" in trace.events[-1].detail

    def test_details_are_redacted(self):
        recorder = TraceRecorder("b-1")
        recorder.escalation_started(
            JourneyStep.OPEN_HOME, "cookie=abcdef0123456789abcdef0123456789"
        )
        trace = recorder.finish(_failure_result())
        assert "abcdef0123456789" not in trace.events[0].detail
        assert "[REDACTED]" in trace.events[0].detail


class TestRedact:
    def test_token_material_removed(self):
        assert "[REDACTED]" in redact("authorization: Bearer0123456789abcdef")
        assert "secret123" in redact("secret123")  # short strings untouched

    def test_plain_text_untouched(self):
        text = "Standard Double € 350.00 Free cancellation"
        assert redact(text) == text

    def test_anthropic_key_redacted_even_without_a_label(self):
        # bolt 009 (US-027): a personal key can appear bare in an error
        # message, not just after "key=" — must still be redacted.
        text = "anthropic.AuthenticationError: sk-ant-api03-abc123DEF456ghi789 is invalid"
        redacted = redact(text)
        assert "sk-ant-api03-abc123DEF456ghi789" not in redacted
        assert "[REDACTED]" in redacted

    def test_anthropic_key_redacted_with_key_equals_label(self):
        redacted = redact("api_key=sk-ant-api03-abcdefghijklmnop")
        assert "sk-ant-api03-abcdefghijklmnop" not in redacted


class TestSnapshotWriter:
    def test_writes_text_and_optional_png(self, tmp_path):
        writer = SnapshotWriter(tmp_path / "snapshots")
        writer.write_failure("chk-1", "page text", screenshot=b"png-bytes")
        assert (tmp_path / "snapshots" / "chk-1.txt").read_text() == "page text"
        assert (tmp_path / "snapshots" / "chk-1.png").read_bytes() == b"png-bytes"

    def test_snapshot_content_redacted(self, tmp_path):
        writer = SnapshotWriter(tmp_path / "snapshots")
        writer.write_failure("chk-1", "session cookie=abcdef0123456789abcdef")
        content = (tmp_path / "snapshots" / "chk-1.txt").read_text()
        assert "abcdef0123456789" not in content

    def test_rotation_keeps_newest(self, tmp_path):
        import time

        writer = SnapshotWriter(tmp_path / "snapshots", max_files=3)
        for i in range(6):
            writer.write_failure(f"chk-{i}", f"text {i}")
            time.sleep(0.01)  # distinct mtimes so rotation order is deterministic
        remaining = sorted(p.name for p in (tmp_path / "snapshots").iterdir())
        assert len(remaining) == 3
        assert "chk-5.txt" in remaining
        assert "chk-0.txt" not in remaining

    def test_write_errors_never_raise(self, tmp_path):
        target = tmp_path / "not-a-dir"
        target.write_text("file blocks mkdir")
        writer = SnapshotWriter(target / "snapshots")
        writer.write_failure("chk-1", "text")  # must not raise
