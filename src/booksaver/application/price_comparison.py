"""Paired price-method comparison: the side-effect-free Jev arm and the two-result report.

The existing check path remains the only authority for canonical history, sessions, savings, and
alerts.  This module runs the experimental Jev arm from the same frozen booking inputs and session
snapshot, evaluates it with the same validators and offer selection, and formats one caller-scoped
Telegram report that shows both methods side by side.
"""

from __future__ import annotations

import logging
import math
from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from typing import Protocol

from booksaver.application.browser_executor import (
    AgenticPriceExecutionService,
    InMemorySessionLeaseBroker,
    OwnerBoundAgenticPriceCheck,
    PriceExecutionOutcome,
)
from booksaver.domain.browser_executor import (
    MAX_EXECUTOR_ACTIONS,
    ExecutionLimits,
    PriceExecutionRequest,
    PriceExecutionResult,
)
from booksaver.domain.check_result import CheckOutcome, CheckResult
from booksaver.domain.model_policy import UsdAmount
from booksaver.domain.models import Booking
from booksaver.domain.price_comparison import (
    ArmResult,
    ArmStatus,
    ComparisonArm,
    ComparisonTrigger,
    CostCertainty,
    JevComparisonSettings,
    JevUsage,
    format_usd_nano,
    micro_usd_to_nano,
)
from booksaver.domain.savings import SavingsOpportunity, detect_savings
from booksaver.domain.value_objects import Money

logger = logging.getLogger(__name__)

_MIN_ARM_SECONDS = 30


class JevPriceExecutorPort(Protocol):
    last_usage: JevUsage

    def execute(self, request: PriceExecutionRequest) -> PriceExecutionResult: ...


OutcomeEvaluator = Callable[[Booking, PriceExecutionOutcome, str], CheckResult]


def _savings(booking: Booking, result: CheckResult) -> tuple[Money | None, str | None]:
    if result.outcome is not CheckOutcome.SUCCESS or result.live_price is None:
        return None, None
    opportunity = detect_savings(booking, result)
    if isinstance(opportunity, SavingsOpportunity):
        return opportunity.amount_saved, None
    return None, opportunity.value


def arm_from_check(
    arm: ComparisonArm,
    booking: Booking,
    result: CheckResult,
    *,
    started_at: datetime,
    finished_at: datetime,
    model_calls: int,
    input_tokens: int,
    output_tokens: int,
    cost_nano_usd: int | None,
    certainty: CostCertainty,
) -> ArmResult:
    success = result.outcome is CheckOutcome.SUCCESS and result.live_price is not None
    failure = result.failure_reason
    savings, savings_rejection = _savings(booking, result) if success else (None, None)
    return ArmResult(
        arm=arm,
        status=ArmStatus.SUCCESS if success else ArmStatus.FAILURE,
        outcome_code="success" if success else (failure.code.value if failure else "unknown"),
        started_at=started_at,
        finished_at=max(started_at, finished_at),
        live_price=result.live_price if success else None,
        room_label=(
            result.extracted_fields.room_label if result.extracted_fields is not None else None
        ),
        refund_text=(
            result.refund_indicators.raw_text if result.refund_indicators is not None else None
        ),
        savings=savings,
        savings_rejection=savings_rejection,
        model_calls=model_calls,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cost_nano_usd=cost_nano_usd,
        cost_certainty=certainty,
        detail="" if success or failure is None else failure.detail[:300],
    )


def baseline_arm(
    booking: Booking,
    result: CheckResult,
    outcome: PriceExecutionOutcome | None,
    *,
    started_at: datetime,
    finished_at: datetime,
) -> ArmResult:
    usage = outcome.result.usage if outcome is not None else None
    return arm_from_check(
        ComparisonArm.BASELINE,
        booking,
        result,
        started_at=started_at,
        finished_at=finished_at,
        model_calls=usage.model_calls if usage is not None else 0,
        input_tokens=usage.tokens.input_tokens if usage is not None else 0,
        output_tokens=usage.tokens.output_tokens if usage is not None else 0,
        cost_nano_usd=micro_usd_to_nano(usage.cost.micro_usd) if usage is not None else None,
        certainty=CostCertainty.EXACT if usage is not None else CostCertainty.UNKNOWN,
    )


def not_run_arm(arm: ComparisonArm, reason: str, detail: str, now: datetime) -> ArmResult:
    return ArmResult(
        arm=arm,
        status=ArmStatus.NOT_RUN,
        outcome_code=reason,
        started_at=now,
        finished_at=now,
        cost_nano_usd=0,
        cost_certainty=CostCertainty.EXACT,
        detail=detail,
    )


@dataclass(frozen=True, slots=True)
class JevArmRequest:
    user_id: int
    booking: Booking
    session_material: bytes
    session_revision_id: str
    deadline: datetime
    remaining_daily_nano_usd: int


def _with_diagnostic(arm: ArmResult, executor: JevPriceExecutorPort) -> ArmResult:
    """Keep the executor's content-free account of the run with its comparison record.

    The detail is stored for the operator and never shown in the Telegram report. It leads the
    text so later truncation cannot drop it.
    """

    diagnostic = str(getattr(executor, "last_diagnostic", "") or "")
    if not diagnostic:
        return arm
    return replace(arm, detail=f"[{diagnostic}] {arm.detail}".strip())


class JevArmRunner:
    """Run one Jev price arm with a fresh lease; never touches canonical state."""

    def __init__(
        self,
        *,
        settings: JevComparisonSettings,
        executor_factory: Callable[[InMemorySessionLeaseBroker, int], JevPriceExecutorPort],
        evaluate: OutcomeEvaluator,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._settings = settings
        self._executor_factory = executor_factory
        self._evaluate = evaluate
        self._clock = clock or (lambda: datetime.now(UTC))

    def run(self, request: JevArmRequest) -> ArmResult:
        started = self._clock()
        if request.remaining_daily_nano_usd <= 0:
            return not_run_arm(
                ComparisonArm.JEV,
                "daily_cost_limit",
                "The experiment's daily Jev spending cap was reached.",
                started,
            )
        deadline = min(
            request.deadline, started + timedelta(seconds=self._settings.arm_timeout_seconds)
        )
        seconds = int((deadline - started).total_seconds())
        if seconds < _MIN_ARM_SECONDS:
            return not_run_arm(
                ComparisonArm.JEV,
                "time_limit",
                "Not enough of this check's time allowance remained for the Jev method.",
                started,
            )
        cap_nano = request.remaining_daily_nano_usd
        limits = ExecutionLimits(
            deadline=deadline,
            max_actions=MAX_EXECUTOR_ACTIONS,
            max_computer_use_actions=0,
            timeout_seconds=seconds,
            max_job_cost=UsdAmount(max(1, min(1_000_000, math.ceil(cap_nano / 1_000)))),
        )
        broker = InMemorySessionLeaseBroker()
        executor = self._executor_factory(broker, cap_nano)
        check = OwnerBoundAgenticPriceCheck(AgenticPriceExecutionService(executor, broker), broker)
        try:
            # The candidate's refreshed session (if any) is discarded: only the baseline arm may
            # update the owner's saved Booking.com session.
            outcome = check.execute(
                owner_user_id=request.user_id,
                booking=request.booking,
                session_material=request.session_material,
                limits=limits,
            )
            result = self._evaluate(request.booking, outcome, request.session_revision_id)
        except Exception as exc:
            usage = executor.last_usage
            logger.warning(
                "Jev comparison arm failed booking=%s failure_type=%s",
                request.booking.booking_id,
                type(exc).__name__,
            )
            failed = ArmResult(
                arm=ComparisonArm.JEV,
                status=ArmStatus.FAILURE,
                outcome_code="infrastructure_failure",
                started_at=started,
                finished_at=max(started, self._clock()),
                model_calls=usage.calls,
                input_tokens=usage.input_tokens,
                output_tokens=usage.output_tokens,
                cost_nano_usd=usage.cost_nano_usd,
                cost_certainty=usage.certainty,
                detail=f"The Jev method stopped after {type(exc).__name__}.",
            )
            return _with_diagnostic(failed, executor)
        usage = executor.last_usage
        logger.info(
            "Jev comparison arm booking=%s status=%s rejection=%s offers=%s rejected_offers=%s "
            "calls=%s input_tokens=%s cost_nano_usd=%s certainty=%s",
            request.booking.booking_id,
            outcome.result.status.value,
            outcome.validation.rejection.value if outcome.validation.rejection else "none",
            len(outcome.result.offers),
            outcome.validation.rejected_offer_count,
            usage.calls,
            usage.input_tokens,
            usage.cost_nano_usd,
            usage.certainty.value,
        )
        arm = arm_from_check(
            ComparisonArm.JEV,
            request.booking,
            result,
            started_at=started,
            finished_at=self._clock(),
            model_calls=usage.calls,
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            cost_nano_usd=usage.cost_nano_usd,
            certainty=usage.certainty,
        )
        return _with_diagnostic(arm, executor)


_REASONS = {
    "no_equivalent_offer": "no matching refundable, tax-inclusive offer was verified",
    "extraction_failed": "the page's stay facts could not be verified",
    "property_not_found": "the property could not be confirmed",
    "step_failed": "the stay dates could not be confirmed",
    "occupancy_missing": "the guest count could not be confirmed",
    "currency_mismatch": "the currency did not match your booking",
    "auth_required": "Booking.com sign-in could not be confirmed",
    "provider_unavailable": "the AI provider or its browser session failed",
    "provider_authentication": "the AI provider rejected its credentials",
    "budget_exceeded": "its spending or action limit was reached",
    "timeout": "it ran out of time",
    "bot_wall": "Booking.com blocked the browser",
    "blocked_action": "an unsafe action was blocked",
    "infrastructure_failure": "the browser stopped unexpectedly",
    "daily_cost_limit": "the daily experiment cap was reached",
    "time_limit": "not enough time remained",
    "stopping": "BookSaver was shutting down",
    "caller_revoked": "access changed during the check",
    "baseline_blocked": "Booking.com blocked the existing method's session first",
}


def _money(value: Money) -> str:
    return f"{value.amount:,.2f} {value.currency}"


def _arm_lines(label: str, arm: ArmResult, booking: Booking) -> list[str]:
    if arm.status is ArmStatus.SUCCESS:
        assert arm.live_price is not None
        booked = _money(booking.baseline_price)
        if arm.savings is not None:
            comparison = f"{_money(arm.savings)} below your booked {booked}"
        elif arm.savings_rejection not in (None, "price_not_lower"):
            reason = str(arm.savings_rejection).replace("_", " ")
            comparison = f"not counted as a saving versus your booked {booked} ({reason})"
        else:
            comparison = f"no lower than your booked {booked}"
        headline = f"{label}: {_money(arm.live_price)} · {comparison}"
    elif arm.status is ArmStatus.NOT_RUN:
        headline = f"{label}: not run — {_REASONS.get(arm.outcome_code, arm.outcome_code)}"
    else:
        reason = _REASONS.get(arm.outcome_code, arm.outcome_code.replace("_", " "))
        headline = f"{label}: could not verify a price — {reason}"
    cost = format_usd_nano(arm.cost_nano_usd, arm.cost_certainty)
    detail = f"   AI cost {cost} · {arm.elapsed_seconds:.0f}s"
    if arm.model_calls:
        detail += f" · {arm.model_calls} model calls"
    return [headline, detail]


def format_comparison_report(
    *,
    booking: Booking,
    trigger: ComparisonTrigger,
    comparison_id: str,
    first_arm: ComparisonArm,
    baseline: ArmResult,
    jev: ArmResult,
) -> tuple[str, str]:
    stay = booking.stay_dates
    subject = (
        f"BookSaver price comparison · {booking.property.name} · "
        f"{stay.check_in:%b %d}–{stay.check_out:%b %d}"
    )
    lines = [
        *_arm_lines("Existing method (Claude)", baseline, booking),
        "",
        *_arm_lines("Jev (experimental)", jev, booking),
        "",
    ]
    if baseline.status is ArmStatus.SUCCESS and jev.status is ArmStatus.SUCCESS:
        assert baseline.live_price is not None and jev.live_price is not None
        if baseline.live_price == jev.live_price:
            lines.append("Both methods verified the same price.")
        else:
            lines.append("The methods verified different prices; Booking.com may have changed.")
    gap = abs((jev.started_at - baseline.started_at).total_seconds())
    lines.append(
        f"{'Scheduled' if trigger is ComparisonTrigger.SCHEDULED else 'Manual'} check · "
        f"{'Jev' if first_arm is ComparisonArm.JEV else 'existing method'} ran first · "
        f"runs started {gap / 60:.0f} min apart · ref {comparison_id[:8]}"
    )
    lines.append(
        "Only the existing method's result is saved and can trigger savings alerts."
    )
    return subject, "\n".join(lines)
