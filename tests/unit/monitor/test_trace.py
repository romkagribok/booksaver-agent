from __future__ import annotations

import json
from datetime import UTC, datetime
from decimal import Decimal

from booksaver.domain.agent import (
    AgentAction,
    AgentActionType,
    AgentHistoryEvent,
    AgentHistoryOutcome,
    AgentStopReason,
    TraceKind,
)
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
        recorder.currency_alignment("requested=EUR observed=USD; recovery started")
        recorder.escalation_started(JourneyStep.FILL_SEARCH, "selector missing")
        recorder.agent_action(
            JourneyStep.FILL_SEARCH,
            AgentAction(type=AgentActionType.CLICK, ref="e0"),
            tier2=False,
            target_label="Check available dates",
        )
        recorder.agent_result(JourneyStep.FILL_SEARCH, "step completed by agent")
        result = _success_result()
        trace = recorder.finish(result)

        assert [e.seq for e in trace.events] == [0, 1, 2, 3, 4, 5]
        assert [e.kind for e in trace.events] == [
            TraceKind.JOURNEY_STEP,
            TraceKind.CURRENCY_ALIGNMENT,
            TraceKind.ESCALATION_STARTED,
            TraceKind.AGENT_ACTION,
            TraceKind.AGENT_RESULT,
            TraceKind.CHECK_RESULT,
        ]
        assert trace.check_id == result.check_id
        assert trace.booking_id == "b-1"
        assert "requested=EUR observed=USD" in trace.events[1].detail
        assert json.loads(trace.events[3].detail) == {
            "action": "click",
            "step": "fill_search",
            "target_present": True,
            "tier": 1,
            "value_present": False,
        }
        assert "e0" not in trace.events[3].detail
        assert "Check available dates" not in trace.events[3].detail
        assert "step completed by agent" not in trace.events[4].detail
        assert "350.00 EUR via agent" in trace.events[-1].detail

    def test_failure_result_recorded_with_code(self):
        recorder = TraceRecorder("b-1")
        trace = recorder.finish(_failure_result())
        assert "agent_gave_up" in trace.events[-1].detail

    def test_agent_outcome_records_structured_redacted_recovery_facts(self):
        recorder = TraceRecorder("b-1")
        recorder.agent_outcome(
            JourneyStep.FILL_SEARCH,
            AgentHistoryEvent(
                outcome=AgentHistoryOutcome.EXECUTED,
                detail="page unchanged token=abcdef0123456789abcdef",
                action=AgentAction(
                    type=AgentActionType.CLICK,
                    ref="volatile-e47",
                    value="private action value",
                ),
                semantic_target="click|button|Check dates",
                popup_opened=True,
            ),
            no_progress_count=2,
            semantic_execution_count=2,
            stop_reason=AgentStopReason.NO_PROGRESS,
        )

        trace = recorder.finish(_failure_result())
        outcome = trace.events[0]
        payload = json.loads(outcome.detail)

        assert outcome.kind is TraceKind.AGENT_OUTCOME
        assert payload == {
            "content_changed": False,
            "detail": "page unchanged token=[REDACTED]",
            "elements_changed": False,
            "executed": True,
            "no_progress_count": 2,
            "outcome": "executed",
            "popup_opened": True,
            "progress": False,
            "scroll_changed": False,
            "semantic_execution_count": 2,
            "step": "fill_search",
            "stop_reason": "no_progress",
            "url_changed": False,
            "verified": False,
        }
        assert "volatile-e47" not in outcome.detail
        assert "private action value" not in outcome.detail
        assert "click|button|Check dates" not in outcome.detail
        assert "abcdef0123456789abcdef" not in outcome.detail

    def test_agent_outcome_records_progress_and_provider_error_without_raw_action(self):
        recorder = TraceRecorder("b-1")
        recorder.agent_outcome(
            JourneyStep.LOCATE_PROPERTY,
            AgentHistoryEvent(
                outcome=AgentHistoryOutcome.FAILED,
                detail="provider call failed",
                action=AgentAction(type=AgentActionType.CLICK, ref="e9"),
                goal_verified=True,
                url_changed=True,
                error="authorization: abcdef0123456789abcdef",
            ),
            stop_reason=AgentStopReason.PROVIDER_ERROR,
        )

        payload = json.loads(recorder.finish(_failure_result()).events[0].detail)

        assert payload["outcome"] == "failed"
        assert payload["executed"] is False
        assert payload["progress"] is True
        assert payload["verified"] is True
        assert payload["stop_reason"] == "provider_error"
        assert payload["error"] == "authorization: [REDACTED]"
        assert "e9" not in json.dumps(payload)

    def test_stopped_outcome_and_result_do_not_persist_stop_detail(self):
        recorder = TraceRecorder("b-1")
        stop_detail = (
            "agent stopped for Confirmation 987654321 at Private Hotel "
            "token=abcdef0123456789abcdef "
            + "x" * 800
        )
        recorder.agent_outcome(
            JourneyStep.LOCATE_PROPERTY,
            AgentHistoryEvent(
                outcome=AgentHistoryOutcome.STOPPED,
                detail=stop_detail,
            ),
            stop_reason=AgentStopReason.NO_PROGRESS,
        )
        recorder.agent_result(JourneyStep.LOCATE_PROPERTY, stop_detail)

        trace = recorder.finish(_failure_result())
        outcome = json.loads(trace.events[0].detail)
        result = json.loads(trace.events[1].detail)

        assert outcome["stop_reason"] == "no_progress"
        assert len(outcome["detail_digest"]) == 64
        assert len(result["detail_digest"]) == 64
        for event in trace.events[:2]:
            assert "987654321" not in event.detail
            assert "Private Hotel" not in event.detail
            assert "abcdef0123456789abcdef" not in event.detail

    def test_blocked_trace_digests_rendered_labels_hrefs_and_identifiers(self):
        recorder = TraceRecorder("b-1")
        raw_reason = (
            "target label 'Cancel reservation 987654321 for Private Guest' "
            "at https://secure.booking.com/cancel?token=abcdef0123456789abcdef "
            "is reservation-mutating"
        )

        recorder.agent_blocked(JourneyStep.LOCATE_PROPERTY, raw_reason)

        event = recorder.finish(_failure_result()).events[0]
        payload = json.loads(event.detail)
        assert event.kind is TraceKind.AGENT_BLOCKED
        assert payload["step"] == "locate_property"
        assert len(payload["reason_digest"]) == 64
        for sensitive in (
            "Cancel reservation",
            "987654321",
            "Private Guest",
            "secure.booking.com",
            "abcdef0123456789abcdef",
        ):
            assert sensitive not in event.detail

    def test_operational_export_is_bounded_and_omits_free_form_evidence(self):
        recorder = TraceRecorder("b-1")
        recorder.escalation_started(
            JourneyStep.LOCATE_PROPERTY,
            "Private Hotel https://booking.com/confirmation/987654321",
        )
        recorder.agent_outcome(
            JourneyStep.LOCATE_PROPERTY,
            AgentHistoryEvent(
                outcome=AgentHistoryOutcome.FAILED,
                detail="Private Guest confirmation 987654321",
                action=AgentAction(
                    type=AgentActionType.CLICK,
                    ref="e-private",
                    value="private value",
                ),
                error="https://booking.com/private?token=abcdefghijklmnop",
            ),
            no_progress_count=1,
        )
        recorder.agent_blocked(
            JourneyStep.LOCATE_PROPERTY,
            "Cancel reservation for Private Guest at /confirmation/987654321",
        )

        exported = recorder.export_operational_events(max_events=2)

        assert len(exported) == 2
        assert exported[0] == {
            "kind": "agent_outcome",
            "step": "locate_property",
            "outcome": "failed",
            "executed": False,
            "progress": False,
            "verified": False,
            "url_changed": False,
            "content_changed": False,
            "elements_changed": False,
            "scroll_changed": False,
            "popup_opened": False,
            "no_progress_count": 1,
        }
        assert exported[1]["kind"] == "agent_blocked"
        rendered = json.dumps(exported)
        for sensitive in (
            "Private Hotel",
            "Private Guest",
            "987654321",
            "e-private",
            "private value",
            "booking.com/private",
        ):
            assert sensitive not in rendered

    def test_operational_export_rejects_non_positive_limit(self):
        recorder = TraceRecorder("b-1")
        try:
            recorder.export_operational_events(max_events=0)
        except ValueError as exc:
            assert "max_events" in str(exc)
        else:
            raise AssertionError("expected non-positive export limit to be rejected")

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
