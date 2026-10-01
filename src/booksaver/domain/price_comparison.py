"""Paired price-method comparison contracts (intent 026).

A comparison runs the existing price method (baseline) and the experimental Jev method against
the same trusted booking inputs.  Only the baseline arm owns canonical effects; the Jev arm is
recorded here and reported to the booking owner as experimental information.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum

from .value_objects import Money

JEV_MODEL = "jev-1.13.0"
JEV_PRICE_TABLE_VERSION = "typesafe-2026-09-27"
# TypeSafe publishes USD 0.042 per million input tokens and free output tokens.  One input token
# therefore costs 42 nano-USD; the ledger keeps nano-USD so cheap calls never round to zero.
JEV_NANO_USD_PER_INPUT_TOKEN = 42
JEV_ADAPTER_VERSION = "jev-price-v2"
MAX_JEV_CALLS_PER_ARM = 120
MAX_JEV_ARM_SECONDS = 180
MAX_JEV_DAILY_COST_NANO_USD = 1_000_000_000  # USD 1.00


class ComparisonArm(Enum):
    BASELINE = "baseline"
    JEV = "jev"


class ComparisonTrigger(Enum):
    CHECK_NOW = "check_now"
    SCHEDULED = "scheduled"


class ArmStatus(Enum):
    SUCCESS = "success"
    FAILURE = "failure"
    NOT_RUN = "not_run"


class CostCertainty(Enum):
    EXACT = "exact"
    CONSERVATIVE = "conservative"
    UNKNOWN = "unknown"


class ComparisonParticipants(Enum):
    OWNER = "owner"
    ALL = "all"

    @classmethod
    def parse(cls, raw: object) -> ComparisonParticipants:
        try:
            return cls(str(raw).strip().lower())
        except ValueError as exc:
            raise ValueError("jev_comparison.participants must be one of: owner, all") from exc


@dataclass(frozen=True, slots=True)
class JevComparisonSettings:
    """Explicit, capped activation of the paired Jev experiment.  Disabled by default."""

    enabled: bool = False
    participants: ComparisonParticipants = ComparisonParticipants.OWNER
    model: str = JEV_MODEL
    max_calls_per_arm: int = 100
    arm_timeout_seconds: int = 150
    max_daily_cost_nano_usd: int = 250_000_000  # USD 0.25

    def __post_init__(self) -> None:
        if self.model != JEV_MODEL:
            raise ValueError(f"jev_comparison.model must be the pinned {JEV_MODEL}")
        if not 1 <= self.max_calls_per_arm <= MAX_JEV_CALLS_PER_ARM:
            raise ValueError(
                f"jev_comparison.max_calls_per_arm must be between 1 and {MAX_JEV_CALLS_PER_ARM}"
            )
        if not 30 <= self.arm_timeout_seconds <= MAX_JEV_ARM_SECONDS:
            raise ValueError(
                "jev_comparison.arm_timeout_seconds must be between 30 and "
                f"{MAX_JEV_ARM_SECONDS}"
            )
        if not 1 <= self.max_daily_cost_nano_usd <= MAX_JEV_DAILY_COST_NANO_USD:
            raise ValueError(
                "jev_comparison.max_daily_cost_usd must be greater than zero and at most 1.00"
            )

    def admits(self, *, is_owner: bool) -> bool:
        return self.enabled and (is_owner or self.participants is ComparisonParticipants.ALL)


@dataclass(frozen=True, slots=True)
class JevUsage:
    """Exact TypeSafe usage for one arm; nano-USD keeps sub-microdollar calls visible."""

    calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cost_nano_usd: int = 0
    certainty: CostCertainty = CostCertainty.EXACT

    def __post_init__(self) -> None:
        for name in ("calls", "input_tokens", "output_tokens", "cost_nano_usd"):
            value = getattr(self, name)
            if isinstance(value, bool) or value < 0:
                raise ValueError(f"{name} must be a non-negative integer")


def jev_cost_nano_usd(input_tokens: int) -> int:
    if isinstance(input_tokens, bool) or input_tokens < 0:
        raise ValueError("input_tokens must be a non-negative integer")
    return input_tokens * JEV_NANO_USD_PER_INPUT_TOKEN


@dataclass(frozen=True, slots=True)
class ArmResult:
    """One method's terminal outcome.  Failures are never converted into "no savings"."""

    arm: ComparisonArm
    status: ArmStatus
    outcome_code: str
    started_at: datetime
    finished_at: datetime
    live_price: Money | None = None
    room_label: str | None = None
    refund_text: str | None = None
    savings: Money | None = None
    # Why a verified price is not reported as a saving (e.g. room_differs), when applicable.
    savings_rejection: str | None = None
    model_calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cost_nano_usd: int | None = None
    cost_certainty: CostCertainty = CostCertainty.UNKNOWN
    detail: str = ""

    def __post_init__(self) -> None:
        if self.status is ArmStatus.SUCCESS and self.live_price is None:
            raise ValueError("a successful arm requires a validated live price")
        if self.status is not ArmStatus.SUCCESS and (
            self.live_price is not None or self.savings is not None
        ):
            raise ValueError("only a successful arm may carry a price or savings")
        if self.finished_at < self.started_at:
            raise ValueError("arm cannot finish before it started")
        if self.cost_nano_usd is not None and self.cost_nano_usd < 0:
            raise ValueError("arm cost cannot be negative")

    @property
    def elapsed_seconds(self) -> float:
        return (self.finished_at - self.started_at).total_seconds()


def micro_usd_to_nano(micro_usd: int) -> int:
    return micro_usd * 1_000


def format_usd_nano(nano_usd: int | None, certainty: CostCertainty) -> str:
    """Render a model cost with enough precision that cheap calls stay visible."""

    if nano_usd is None or certainty is CostCertainty.UNKNOWN:
        return "unknown"
    dollars = Decimal(nano_usd) / Decimal(1_000_000_000)
    if nano_usd == 0:
        text = "$0"
    elif dollars < Decimal("0.0001"):
        text = "< $0.0001"
    elif dollars < Decimal("0.01"):
        text = f"${dollars.quantize(Decimal('0.0001'))}"
    else:
        text = f"${dollars.quantize(Decimal('0.001'))}"
    return f"{text} (upper bound)" if certainty is CostCertainty.CONSERVATIVE else text
