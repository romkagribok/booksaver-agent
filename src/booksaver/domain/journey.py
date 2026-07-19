from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .check_result import FailureCode


class JourneyStep(Enum):
    """Named steps of the Booking.com search journey, in execution order (ADR-013).

    Step names are stable identifiers: they appear in failure details, logs, and
    (bolt 007) traces, and each is an escalation seam for the LLM browser agent.
    """

    OPEN_HOME = "open_home"
    DISMISS_OVERLAYS = "dismiss_overlays"
    FILL_SEARCH = "fill_search"
    SUBMIT_SEARCH = "submit_search"
    LOCATE_PROPERTY = "locate_property"
    OPEN_PROPERTY = "open_property"
    VERIFY_CONTEXT = "verify_context"
    READ_ROOM_TABLE = "read_room_table"
    ALIGN_CURRENCY = "align_currency"


@dataclass(frozen=True)
class StepOutcome:
    step: JourneyStep
    ok: bool
    detail: str = ""

    @classmethod
    def success(cls, step: JourneyStep, detail: str = "") -> StepOutcome:
        return cls(step=step, ok=True, detail=detail)

    @classmethod
    def failed(cls, step: JourneyStep, detail: str) -> StepOutcome:
        return cls(step=step, ok=False, detail=detail)


@dataclass(frozen=True)
class JourneyResult:
    """Terminal state of one journey run: every executed step plus how it ended."""

    outcomes: tuple[StepOutcome, ...]
    failure_code: FailureCode | None = None
    agent_assisted: bool = False  # any step needed LLM-agent takeover (bolt 007)

    @property
    def ok(self) -> bool:
        return self.failure_code is None

    @property
    def failed_step(self) -> StepOutcome | None:
        for outcome in self.outcomes:
            if not outcome.ok:
                return outcome
        return None
