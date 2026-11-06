from __future__ import annotations

import json
import logging
import re
from collections.abc import Callable, Sequence
from datetime import UTC, datetime

from booksaver.application.browser_executor import PriceExecutionOutcome
from booksaver.domain.agent import CheckTrace, TraceEvent, TraceKind
from booksaver.domain.check_result import CheckResult
from booksaver.domain.models import Booking
from booksaver.domain.offer import OfferCandidate, OfferSelection
from booksaver.monitor.price_diagnostics import price_validation_diagnostics

logger = logging.getLogger(__name__)

# Cookie/token-shaped material must never reach traces (US-022).
_SECRET_PATTERN = re.compile(
    r"((?:cookie|token|secret|password|authorization)\s*[=:]\s*)\S{16,}", re.IGNORECASE
)

# Retired provider API keys (`sk-ant-...`) stay redacted unconditionally, so
# old text that reaches a trace can never expose one.
_PROVIDER_KEY_PATTERN = re.compile(r"sk-ant-[A-Za-z0-9_-]{10,}")


def redact(text: str) -> str:
    text = _SECRET_PATTERN.sub(r"\1[REDACTED]", text)
    return _PROVIDER_KEY_PATTERN.sub("[REDACTED]", text)


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

    def price_validation(
        self,
        booking: Booking,
        outcome: PriceExecutionOutcome,
        candidates: Sequence[OfferCandidate],
        selection: OfferSelection | None,
        normalize_room: Callable[[str], str],
    ) -> None:
        try:
            payload = price_validation_diagnostics(
                booking, outcome, candidates, selection, normalize_room,
            )
        except Exception as exc:
            # Optional diagnostics must never change the actual acceptance decision.
            logger.warning("Price validation diagnostics unavailable: %s", type(exc).__name__)
            return
        self._add(
            TraceKind.PRICE_VALIDATION,
            json.dumps(payload, sort_keys=True, separators=(",", ":")),
            detail_is_redacted=True,
        )

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
