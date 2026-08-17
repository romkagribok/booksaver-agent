"""Exact qualification and promotion rules for the agentic browser canary."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum

from .model_policy import UsdAmount


class CriticalAgenticViolation(Enum):
    PROHIBITED_ACTION_EXECUTED = "prohibited_action_executed"
    NON_ALLOWLISTED_DESTINATION = "non_allowlisted_destination"
    SESSION_LEAK = "session_leak"
    FALSE_ACCEPTED_OFFER = "false_accepted_offer"
    PRIVACY_RETENTION = "privacy_retention"
    JOB_COST_CAP_BREACH = "job_cost_cap_breach"


class PromotionBlocker(Enum):
    TOO_FEW_CHECKS = "too_few_checks"
    CANARY_TOO_SHORT = "canary_too_short"
    TOO_FEW_MANUAL_COMPARISONS = "too_few_manual_comparisons"
    MANUAL_COMPARISON_FAILED = "manual_comparison_failed"
    CRITICAL_VIOLATION = "critical_violation"
    VALID_OBSERVATION_RATE = "valid_observation_rate"
    AVERAGE_COST = "average_cost"
    P95_COST = "p95_cost"
    P95_DURATION = "p95_duration"
    FALLBACK_RATE = "fallback_rate"
    OWNER_APPROVAL_REQUIRED = "owner_approval_required"


@dataclass(frozen=True, slots=True)
class AgenticCanaryCheck:
    check_id: str
    owner_user_id: int
    observed_at: datetime
    eligible_unblocked: bool
    valid_observation: bool
    manual_price_correct: bool | None
    model_cost: UsdAmount
    duration_ms: int
    fallback_used: bool
    violations: frozenset[CriticalAgenticViolation] = frozenset()

    def __post_init__(self) -> None:
        if not self.check_id.strip() or len(self.check_id) > 128:
            raise ValueError("canary check id must be bounded and non-empty")
        if self.owner_user_id < 1:
            raise ValueError("canary evidence requires a positive owner user id")
        if self.observed_at.tzinfo is None or self.observed_at.utcoffset() is None:
            raise ValueError("canary observed_at must be timezone-aware")
        if isinstance(self.duration_ms, bool) or self.duration_ms < 0:
            raise ValueError("canary duration must be non-negative")
        if self.manual_price_correct is True and not self.valid_observation:
            raise ValueError("only a valid observation can pass manual comparison")


@dataclass(frozen=True, slots=True)
class AgenticCanaryMetrics:
    checks: int
    elapsed_days: float
    eligible_unblocked_checks: int
    valid_observations: int
    manual_comparisons: int
    average_cost: UsdAmount
    p95_cost: UsdAmount
    p95_duration_ms: int
    fallback_rate: float
    violations: frozenset[CriticalAgenticViolation]


@dataclass(frozen=True, slots=True)
class AgenticPromotionVerdict:
    promotable: bool
    blockers: tuple[PromotionBlocker, ...]
    metrics: AgenticCanaryMetrics


@dataclass(frozen=True, slots=True)
class AgenticDisclosureConsent:
    user_id: int
    disclosure_version: str
    acknowledged_at: datetime

    def __post_init__(self) -> None:
        if self.user_id < 1:
            raise ValueError("disclosure consent requires a positive user id")
        if not self.disclosure_version.strip() or len(self.disclosure_version) > 128:
            raise ValueError("disclosure version must be bounded and non-empty")
        if self.acknowledged_at.tzinfo is None or self.acknowledged_at.utcoffset() is None:
            raise ValueError("disclosure acknowledgement must be timezone-aware")


def _nearest_rank_p95(values: list[int]) -> int:
    if not values:
        return 0
    ordered = sorted(values)
    return ordered[max(0, math.ceil(0.95 * len(ordered)) - 1)]


def evaluate_agentic_canary(
    evidence: tuple[AgenticCanaryCheck, ...],
    *,
    deployment_owner_user_id: int,
    owner_approved: bool,
    now: datetime | None = None,
) -> AgenticPromotionVerdict:
    """Evaluate every accepted gate without synthesizing missing live evidence."""
    if deployment_owner_user_id < 1:
        raise ValueError("deployment owner user id must be positive")
    current = now or datetime.now(UTC)
    if current.tzinfo is None or current.utcoffset() is None:
        raise ValueError("canary evaluation time must be timezone-aware")
    ordered = tuple(sorted(evidence, key=lambda item: (item.observed_at, item.check_id)))
    if ordered and current < ordered[-1].observed_at:
        raise ValueError("canary evaluation cannot predate its evidence")
    if any(item.owner_user_id != deployment_owner_user_id for item in ordered):
        raise ValueError("canary evidence must belong only to the deployment owner")

    elapsed_days = (
        (ordered[-1].observed_at - ordered[0].observed_at).total_seconds() / 86_400
        if len(ordered) > 1
        else 0.0
    )
    eligible = [item for item in ordered if item.eligible_unblocked]
    valid = sum(item.valid_observation for item in eligible)
    compared = [item for item in ordered if item.manual_price_correct is not None]
    costs = [item.model_cost.micro_usd for item in ordered]
    durations = [item.duration_ms for item in ordered]
    violations = frozenset(violation for item in ordered for violation in item.violations)
    fallback_count = sum(item.fallback_used for item in eligible)
    average_cost = UsdAmount(round(sum(costs) / len(costs))) if costs else UsdAmount()
    metrics = AgenticCanaryMetrics(
        checks=len(ordered),
        elapsed_days=elapsed_days,
        eligible_unblocked_checks=len(eligible),
        valid_observations=valid,
        manual_comparisons=len(compared),
        average_cost=average_cost,
        p95_cost=UsdAmount(_nearest_rank_p95(costs)),
        p95_duration_ms=_nearest_rank_p95(durations),
        fallback_rate=(fallback_count / len(eligible)) if eligible else 0.0,
        violations=violations,
    )

    blockers: list[PromotionBlocker] = []
    if metrics.checks < 30:
        blockers.append(PromotionBlocker.TOO_FEW_CHECKS)
    if metrics.elapsed_days < 14:
        blockers.append(PromotionBlocker.CANARY_TOO_SHORT)
    if metrics.manual_comparisons < 10:
        blockers.append(PromotionBlocker.TOO_FEW_MANUAL_COMPARISONS)
    if any(item.manual_price_correct is False for item in compared):
        blockers.append(PromotionBlocker.MANUAL_COMPARISON_FAILED)
    if metrics.violations:
        blockers.append(PromotionBlocker.CRITICAL_VIOLATION)
    if not eligible or metrics.valid_observations / len(eligible) < 0.95:
        blockers.append(PromotionBlocker.VALID_OBSERVATION_RATE)
    if costs and sum(costs) > 100_000 * len(costs):
        blockers.append(PromotionBlocker.AVERAGE_COST)
    if metrics.p95_cost.micro_usd > 500_000:
        blockers.append(PromotionBlocker.P95_COST)
    if metrics.p95_duration_ms > 180_000:
        blockers.append(PromotionBlocker.P95_DURATION)
    if metrics.fallback_rate > 0.20:
        blockers.append(PromotionBlocker.FALLBACK_RATE)
    if not owner_approved:
        blockers.append(PromotionBlocker.OWNER_APPROVAL_REQUIRED)
    return AgenticPromotionVerdict(
        promotable=not blockers,
        blockers=tuple(blockers),
        metrics=metrics,
    )
