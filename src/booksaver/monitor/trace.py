from __future__ import annotations

import logging
import re
from datetime import UTC, datetime
from pathlib import Path

from booksaver.domain.agent import (
    AgentAction,
    CheckTrace,
    TraceEvent,
    TraceKind,
)
from booksaver.domain.check_result import CheckResult
from booksaver.domain.journey import JourneyStep, StepOutcome

logger = logging.getLogger(__name__)

# Cookie/token-shaped material must never reach traces or snapshots (US-022).
_SECRET_PATTERN = re.compile(
    r"((?:cookie|token|secret|password|authorization)\s*[=:]\s*)\S{16,}", re.IGNORECASE
)


def redact(text: str) -> str:
    return _SECRET_PATTERN.sub(r"\1[REDACTED]", text)


class TraceRecorder:
    """Accumulates the ordered event log of one check (US-022)."""

    def __init__(self, booking_id: str) -> None:
        self._booking_id = booking_id
        self._events: list[TraceEvent] = []

    def _add(self, kind: TraceKind, detail: str) -> None:
        self._events.append(
            TraceEvent(
                seq=len(self._events),
                at=datetime.now(UTC),
                kind=kind,
                detail=redact(detail),
            )
        )

    def journey_step(self, outcome: StepOutcome) -> None:
        status = "ok" if outcome.ok else "FAILED"
        detail = f"{outcome.step.value}: {status}"
        if outcome.detail:
            detail += f" — {outcome.detail}"
        self._add(TraceKind.JOURNEY_STEP, detail)

    def escalation_started(self, step: JourneyStep, trigger: str) -> None:
        self._add(TraceKind.ESCALATION_STARTED, f"{step.value}: {trigger}")

    def agent_action(self, step: JourneyStep, action: AgentAction, tier2: bool) -> None:
        parts = [action.type.value]
        if action.ref:
            parts.append(f"ref={action.ref}")
        if action.value:
            parts.append(f"value={action.value!r}")
        tier = " [tier2]" if tier2 else ""
        self._add(TraceKind.AGENT_ACTION, f"{step.value}: {' '.join(parts)}{tier}")

    def agent_blocked(self, step: JourneyStep, reason: str) -> None:
        self._add(TraceKind.AGENT_BLOCKED, f"{step.value}: {reason}")

    def screenshot_tier(self, step: JourneyStep, reason: str) -> None:
        self._add(TraceKind.SCREENSHOT_TIER, f"{step.value}: {reason}")

    def agent_result(self, step: JourneyStep, detail: str) -> None:
        self._add(TraceKind.AGENT_RESULT, f"{step.value}: {detail}")

    def finish(self, result: CheckResult) -> CheckTrace:
        if result.failure_reason is not None:
            detail = f"failure: {result.failure_reason.code.value} — " \
                     f"{result.failure_reason.detail}"
        else:
            assert result.live_price is not None
            detail = (
                f"success: {result.live_price.amount} {result.live_price.currency}"
                f" via {result.extraction_method.value}"
            )
        self._add(TraceKind.CHECK_RESULT, detail)
        return CheckTrace(
            check_id=result.check_id,
            booking_id=self._booking_id,
            created_at=datetime.now(UTC),
            events=tuple(self._events),
        )


class SnapshotWriter:
    """Failure snapshots under {data_dir}/snapshots/, rotated and redacted (US-022)."""

    def __init__(
        self,
        directory: Path,
        max_files: int = 20,
        max_total_bytes: int = 10 * 1024 * 1024,
    ) -> None:
        self._dir = directory
        self._max_files = max_files
        self._max_total_bytes = max_total_bytes

    def write_failure(
        self, check_id: str, page_text: str, screenshot: bytes | None = None
    ) -> None:
        try:
            self._dir.mkdir(mode=0o700, parents=True, exist_ok=True)
            text_path = self._dir / f"{check_id}.txt"
            text_path.write_text(redact(page_text))
            text_path.chmod(0o600)
            if screenshot:
                png_path = self._dir / f"{check_id}.png"
                png_path.write_bytes(screenshot)
                png_path.chmod(0o600)
            self._rotate()
        except Exception as exc:
            logger.warning("Could not write failure snapshot for %s: %s", check_id, exc)

    def _rotate(self) -> None:
        files = sorted(
            (p for p in self._dir.iterdir() if p.is_file()),
            key=lambda p: p.stat().st_mtime,
            reverse=True,  # newest first
        )
        total = 0
        kept = 0
        for path in files:
            total += path.stat().st_size
            kept += 1
            if kept > self._max_files or total > self._max_total_bytes:
                path.unlink(missing_ok=True)
