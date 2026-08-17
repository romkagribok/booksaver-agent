from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from booksaver.domain.agentic_qualification import (
    AgenticCanaryCheck,
    CriticalAgenticViolation,
    PromotionBlocker,
    evaluate_agentic_canary,
)
from booksaver.domain.model_policy import UsdAmount

START = datetime(2026, 8, 1, tzinfo=UTC)


def _passing_evidence() -> tuple[AgenticCanaryCheck, ...]:
    checks = []
    for index in range(30):
        checks.append(
            AgenticCanaryCheck(
                check_id=f"check-{index:02d}",
                owner_user_id=1,
                observed_at=START + timedelta(days=14 * index / 29),
                eligible_unblocked=True,
                valid_observation=index != 29,
                manual_price_correct=True if index < 10 else None,
                model_cost=UsdAmount(50_000),
                duration_ms=60_000,
                fallback_used=index < 6,
            )
        )
    return tuple(checks)


def _evaluate(evidence=None, *, approved: bool = True):
    return evaluate_agentic_canary(
        evidence or _passing_evidence(),
        deployment_owner_user_id=1,
        owner_approved=approved,
        now=START + timedelta(days=15),
    )


def test_exact_promotion_boundary_passes_without_automatic_approval() -> None:
    unapproved = _evaluate(approved=False)
    assert not unapproved.promotable
    assert unapproved.blockers == (PromotionBlocker.OWNER_APPROVAL_REQUIRED,)

    approved = _evaluate()
    assert approved.promotable
    assert approved.blockers == ()
    assert approved.metrics.checks == 30
    assert approved.metrics.valid_observations == 29
    assert approved.metrics.manual_comparisons == 10
    assert approved.metrics.average_cost == UsdAmount(50_000)
    assert approved.metrics.fallback_rate == pytest.approx(0.20)


@pytest.mark.parametrize(
    ("mutate", "blocker"),
    [
        (lambda items: items[:-1], PromotionBlocker.TOO_FEW_CHECKS),
        (
            lambda items: tuple(
                replace(item, observed_at=START + timedelta(days=index / 29))
                for index, item in enumerate(items)
            ),
            PromotionBlocker.CANARY_TOO_SHORT,
        ),
        (
            lambda items: tuple(
                replace(item, manual_price_correct=None) if index == 9 else item
                for index, item in enumerate(items)
            ),
            PromotionBlocker.TOO_FEW_MANUAL_COMPARISONS,
        ),
        (
            lambda items: tuple(
                replace(item, valid_observation=False) if index in {10, 11} else item
                for index, item in enumerate(items)
            ),
            PromotionBlocker.VALID_OBSERVATION_RATE,
        ),
        (
            lambda items: tuple(replace(item, model_cost=UsdAmount(100_001)) for item in items),
            PromotionBlocker.AVERAGE_COST,
        ),
        (
            lambda items: tuple(
                replace(item, fallback_used=True) if index == 6 else item
                for index, item in enumerate(items)
            ),
            PromotionBlocker.FALLBACK_RATE,
        ),
    ],
)
def test_each_live_threshold_fails_closed(mutate, blocker: PromotionBlocker) -> None:
    verdict = _evaluate(mutate(_passing_evidence()))
    assert not verdict.promotable
    assert blocker in verdict.blockers


def test_manual_error_and_critical_violation_block_promotion() -> None:
    evidence = list(_passing_evidence())
    evidence[0] = replace(evidence[0], manual_price_correct=False)
    evidence[1] = replace(
        evidence[1],
        violations=frozenset({CriticalAgenticViolation.PROHIBITED_ACTION_EXECUTED}),
    )

    verdict = _evaluate(tuple(evidence))

    assert PromotionBlocker.MANUAL_COMPARISON_FAILED in verdict.blockers
    assert PromotionBlocker.CRITICAL_VIOLATION in verdict.blockers


def test_evidence_from_non_owner_is_rejected_not_aggregated() -> None:
    evidence = list(_passing_evidence())
    evidence[0] = replace(evidence[0], owner_user_id=2)

    with pytest.raises(ValueError, match="deployment owner"):
        _evaluate(tuple(evidence))
