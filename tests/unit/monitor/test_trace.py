from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from booksaver.domain.agent import TraceKind
from booksaver.domain.check_result import (
    CheckResult,
    ExtractionMethod,
    FailureCode,
    FailureReason,
)
from booksaver.domain.value_objects import Money
from booksaver.monitor.trace import TraceRecorder, redact


def _success_result() -> CheckResult:
    return CheckResult.success(
        booking_id="b-1",
        checked_at=datetime.now(UTC),
        live_price=Money(amount=Decimal("350.00"), currency="EUR"),
        extraction_method=ExtractionMethod.AGENT,
    )


def _failure_result(detail: str = "stuck") -> CheckResult:
    return CheckResult.failure(
        "b-1",
        datetime.now(UTC),
        FailureReason(code=FailureCode.AGENT_GAVE_UP, detail=detail),
    )


class TestTraceRecorder:
    def test_success_result_is_the_final_typed_event(self):
        result = _success_result()
        trace = TraceRecorder("b-1").finish(result)

        assert [e.kind for e in trace.events] == [TraceKind.CHECK_RESULT]
        assert trace.check_id == result.check_id
        assert trace.booking_id == "b-1"
        assert "350.00 EUR via agent" in trace.events[-1].detail

    def test_failure_result_recorded_with_code(self):
        trace = TraceRecorder("b-1").finish(_failure_result())
        assert "agent_gave_up" in trace.events[-1].detail

    def test_details_are_redacted(self):
        trace = TraceRecorder("b-1").finish(
            _failure_result("cookie=abcdef0123456789abcdef0123456789")
        )
        assert "abcdef0123456789" not in trace.events[-1].detail
        assert "[REDACTED]" in trace.events[-1].detail


class TestRedact:
    def test_token_material_removed(self):
        assert "[REDACTED]" in redact("authorization: Bearer0123456789abcdef")
        assert "secret123" in redact("secret123")  # short strings untouched

    def test_plain_text_untouched(self):
        text = "Standard Double € 350.00 Free cancellation"
        assert redact(text) == text

    def test_retired_provider_key_redacted_even_without_a_label(self):
        text = "AuthenticationError: sk-ant-api03-abc123DEF456ghi789 is invalid"
        redacted = redact(text)
        assert "sk-ant-api03-abc123DEF456ghi789" not in redacted
        assert "[REDACTED]" in redacted

    def test_retired_provider_key_redacted_with_key_equals_label(self):
        redacted = redact("api_key=sk-ant-api03-abcdefghijklmnop")
        assert "sk-ant-api03-abcdefghijklmnop" not in redacted
