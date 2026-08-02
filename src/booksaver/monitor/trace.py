from __future__ import annotations

import hashlib
import json
import logging
import re
from datetime import UTC, datetime
from pathlib import Path

from booksaver.domain.agent import (
    AgentAction,
    AgentHistoryEvent,
    AgentHistoryOutcome,
    AgentStopReason,
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

# Anthropic API keys (owner env-var key or a user's personal `/setkey` key,
# bolt 009 US-027) are shaped like `sk-ant-...` regardless of surrounding
# text, so they're redacted unconditionally rather than only after a
# `key=`/`token=` label — extends the same seam intent 002 built for
# cookies/tokens (US-022).
_ANTHROPIC_KEY_PATTERN = re.compile(r"sk-ant-[A-Za-z0-9_-]{10,}")

_MAX_OUTCOME_SUMMARY_CHARS = 500
_MAX_EXPORTED_OPERATIONAL_EVENTS = 100
_STRUCTURED_OPERATIONAL_KINDS = frozenset(
    {
        TraceKind.AGENT_ACTION,
        TraceKind.AGENT_OUTCOME,
        TraceKind.AGENT_BLOCKED,
        TraceKind.AGENT_RESULT,
    }
)
_SAFE_OPERATIONAL_FIELDS = frozenset(
    {
        "action",
        "content_changed",
        "detail_digest",
        "elements_changed",
        "executed",
        "no_progress_count",
        "outcome",
        "popup_opened",
        "progress",
        "reason_digest",
        "scroll_changed",
        "semantic_execution_count",
        "step",
        "stop_reason",
        "target_present",
        "tier",
        "url_changed",
        "value_present",
        "verified",
    }
)


def redact(text: str) -> str:
    text = _SECRET_PATTERN.sub(r"\1[REDACTED]", text)
    return _ANTHROPIC_KEY_PATTERN.sub("[REDACTED]", text)


def _bounded_redacted(text: str) -> str:
    """Return a trace-safe bounded summary, never raw recovery evidence."""
    return redact(text)[:_MAX_OUTCOME_SUMMARY_CHARS]


def _stable_digest(text: str) -> str:
    """Return a non-reversible stable identifier for sensitive trace detail."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class TraceRecorder:
    """Accumulates the ordered event log of one check (US-022)."""

    def __init__(self, booking_id: str) -> None:
        self._booking_id = booking_id
        self._events: list[TraceEvent] = []

    def _add(
        self, kind: TraceKind, detail: str, *, detail_is_redacted: bool = False
    ) -> None:
        self._events.append(
            TraceEvent(
                seq=len(self._events),
                at=datetime.now(UTC),
                kind=kind,
                detail=detail if detail_is_redacted else redact(detail),
            )
        )

    def journey_step(self, outcome: StepOutcome) -> None:
        status = "ok" if outcome.ok else "FAILED"
        detail = f"{outcome.step.value}: {status}"
        if outcome.detail:
            detail += f" — {outcome.detail}"
        self._add(TraceKind.JOURNEY_STEP, detail)

    def currency_alignment(self, detail: str) -> None:
        self._add(TraceKind.CURRENCY_ALIGNMENT, detail)

    def escalation_started(self, step: JourneyStep, trigger: str) -> None:
        self._add(TraceKind.ESCALATION_STARTED, f"{step.value}: {trigger}")

    def agent_action(
        self,
        step: JourneyStep,
        action: AgentAction,
        tier2: bool,
        target_label: str | None = None,
    ) -> None:
        # Refs are volatile, while labels and values may contain property,
        # confirmation, or user-entered text. Persist only stable operational
        # shape; the controller's guarded in-memory history retains the rest.
        payload = {
            "action": action.type.value,
            "step": step.value,
            "target_present": action.ref is not None or target_label is not None,
            "tier": 2 if tier2 else 1,
            "value_present": bool(action.value),
        }
        self._add(
            TraceKind.AGENT_ACTION,
            json.dumps(payload, sort_keys=True, separators=(",", ":")),
            detail_is_redacted=True,
        )

    def agent_outcome(
        self,
        step: JourneyStep,
        event: AgentHistoryEvent,
        *,
        no_progress_count: int | None = None,
        semantic_execution_count: int | None = None,
        stop_reason: AgentStopReason | None = None,
    ) -> None:
        """Record one structured, redacted recovery outcome (ADR-030).

        The durable trace intentionally omits volatile element refs, action
        values, page-state fingerprints, provider responses, and observations.
        Only bounded operational classifications needed to diagnose recovery
        behavior are retained.
        """
        payload: dict[str, str | bool | int] = {
            "step": step.value,
            "outcome": event.outcome.value,
            "executed": event.outcome is AgentHistoryOutcome.EXECUTED,
            "progress": event.made_progress,
            "verified": event.goal_verified,
            "url_changed": event.url_changed,
            "content_changed": event.content_changed,
            "elements_changed": event.elements_changed,
            "scroll_changed": event.scroll_changed,
            "popup_opened": event.popup_opened,
        }
        if event.detail:
            safe_detail = _bounded_redacted(event.detail)
            if event.outcome is AgentHistoryOutcome.STOPPED:
                payload["detail_digest"] = _stable_digest(safe_detail)
            else:
                payload["detail"] = safe_detail
        if event.error:
            payload["error"] = _bounded_redacted(event.error)
        if no_progress_count is not None:
            payload["no_progress_count"] = no_progress_count
        if semantic_execution_count is not None:
            payload["semantic_execution_count"] = semantic_execution_count
        if stop_reason is not None:
            payload["stop_reason"] = stop_reason.value
        self._add(
            TraceKind.AGENT_OUTCOME,
            json.dumps(payload, sort_keys=True, separators=(",", ":")),
            detail_is_redacted=True,
        )

    def agent_blocked(self, step: JourneyStep, reason: str) -> None:
        # Guard reasons can contain model-selected labels, link destinations,
        # confirmation IDs, or other rendered account data. Persist only a
        # correlation digest and stable classification; the caller may still
        # return the bounded reason in-memory for immediate diagnosis.
        payload = {
            "reason_digest": _stable_digest(_bounded_redacted(reason)),
            "step": step.value,
        }
        self._add(
            TraceKind.AGENT_BLOCKED,
            json.dumps(payload, sort_keys=True, separators=(",", ":")),
            detail_is_redacted=True,
        )

    def screenshot_tier(self, step: JourneyStep, reason: str) -> None:
        self._add(TraceKind.SCREENSHOT_TIER, f"{step.value}: {reason}")

    def agent_result(self, step: JourneyStep, detail: str) -> None:
        # Terminal detail may originate in a provider-selected stop reason.
        # Keep correlation without duplicating model/user text in the trace.
        payload = {
            "detail_digest": _stable_digest(_bounded_redacted(detail)),
            "step": step.value,
        }
        self._add(
            TraceKind.AGENT_RESULT,
            json.dumps(payload, sort_keys=True, separators=(",", ":")),
            detail_is_redacted=True,
        )

    def export_operational_events(
        self, max_events: int = _MAX_EXPORTED_OPERATIONAL_EVENTS
    ) -> tuple[dict[str, str | bool | int], ...]:
        """Export bounded, provider-neutral recovery facts for a local audit.

        This deliberately excludes observations, timestamps, journey evidence,
        raw triggers, provider text, labels, hrefs, action values, and errors.
        Structured recovery events are reduced to an explicit safe field list;
        free-form operational events are represented only by a digest.
        """
        if max_events < 1:
            raise ValueError("max_events must be >= 1")
        limit = min(max_events, _MAX_EXPORTED_OPERATIONAL_EVENTS)
        exported: list[dict[str, str | bool | int]] = []
        for event in self._events:
            if event.kind in _STRUCTURED_OPERATIONAL_KINDS:
                try:
                    parsed = json.loads(event.detail)
                except (TypeError, ValueError, json.JSONDecodeError):
                    parsed = {}
                payload: dict[str, str | bool | int] = {"kind": event.kind.value}
                if isinstance(parsed, dict):
                    for key, value in parsed.items():
                        if key in _SAFE_OPERATIONAL_FIELDS and isinstance(
                            value, (str, bool, int)
                        ):
                            payload[key] = value
                exported.append(payload)
            elif event.kind in {
                TraceKind.ESCALATION_STARTED,
                TraceKind.SCREENSHOT_TIER,
            }:
                exported.append(
                    {
                        "kind": event.kind.value,
                        "detail_digest": _stable_digest(event.detail),
                    }
                )
        return tuple(exported[-limit:])

    def finish(self, result: CheckResult) -> CheckTrace:
        if result.price_source is not None:
            source = result.price_source.as_redacted_dict()
            self._add(
                TraceKind.PRICE_SOURCE,
                "; ".join(f"{key}={value}" for key, value in source.items()),
            )
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
