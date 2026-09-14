from datetime import UTC, datetime, timedelta

from booksaver.daemon.check_coordinator import AgenticBrowserJobContext
from booksaver.domain.browser_executor import ExecutionUsage
from booksaver.domain.inventory_executor import InventoryExecutionLimits
from booksaver.domain.model_policy import BrowserJobKind, UsdAmount


def context(now):
    return AgenticBrowserJobContext(
        local_user_id=4,
        job_kind=BrowserJobKind.CHECK_NOW,
        job_id="job",
        deadline=now + timedelta(seconds=180),
        job_limit_micro_usd=1_000_000,
        daily_limit_micro_usd=10_000_000,
    )


def test_inventory_and_price_share_one_residual_allowance_without_reset():
    now = datetime.now(UTC)
    job = context(now)
    first = job.remaining_limits(now=now, inventory=True)
    assert isinstance(first, InventoryExecutionLimits)
    assert first.max_actions == 40
    job.consume(ExecutionUsage(total_actions=29, computer_use_actions=2, cost=UsdAmount(250_000)))
    price = job.remaining_limits(now=now + timedelta(seconds=70))
    assert price.max_actions == 11
    assert price.timeout_seconds == 110
    assert price.deadline == first.deadline
    assert price.max_job_cost == UsdAmount(750_000)
    assert price.max_computer_use_actions == 4
    job.consume(ExecutionUsage(total_actions=4, computer_use_actions=1, cost=UsdAmount(200_000)))
    second = job.remaining_limits(now=now + timedelta(seconds=90), inventory=True)
    assert second.max_actions == 7
    assert second.max_job_cost == UsdAmount(550_000)
    assert second.max_computer_use_actions == 3
    job.consume(ExecutionUsage(total_actions=7))
    assert job.remaining_limits(now=now + timedelta(seconds=100), inventory=True) is None
    assert job.remaining_limits(now=now + timedelta(seconds=100)) is None


def test_price_keeps_fifteen_action_ceiling_with_or_without_inventory():
    now = datetime.now(UTC)
    standalone = context(now)
    assert standalone.remaining_limits(now=now).max_actions == 15
    standalone.consume(ExecutionUsage(total_actions=15))
    assert standalone.remaining_limits(now=now) is None
    mixed = context(now)
    mixed.remaining_limits(now=now, inventory=True)
    mixed.consume(ExecutionUsage(total_actions=4))
    assert mixed.remaining_limits(now=now).max_actions == 15


def test_combined_operation_grants_fixed_phase_deadlines_with_shared_spend():
    now = datetime.now(UTC)
    job = context(now)
    job.deadline = now + timedelta(seconds=360)
    job.start_phase(now=now)
    inventory = job.remaining_limits(now=now, inventory=True)
    assert inventory.timeout_seconds == 180
    assert inventory.deadline == now + timedelta(seconds=180)
    job.consume(ExecutionUsage(total_actions=29, computer_use_actions=2, cost=UsdAmount(250_000)))
    price_start = now + timedelta(seconds=140)
    job.start_phase(now=price_start)
    price = job.remaining_limits(now=price_start)
    assert price.timeout_seconds == 180
    assert price.deadline == now + timedelta(seconds=320)
    assert price.max_actions == 11
    assert price.max_computer_use_actions == 4
    assert price.max_job_cost == UsdAmount(750_000)
    assert job.job_id == "job"
    # Repeated allowance reads never slide an active phase deadline.
    later = job.remaining_limits(now=now + timedelta(seconds=200))
    assert later.deadline == price.deadline
    assert later.timeout_seconds == 120
    assert job.remaining_limits(now=now + timedelta(seconds=320)) is None
    # A later scheduled price phase gets only the fixed operation's remaining time.
    job.consume(ExecutionUsage(total_actions=4, cost=UsdAmount(100_000)))
    job.start_phase(now=now + timedelta(seconds=330))
    final = job.remaining_limits(now=now + timedelta(seconds=330))
    assert final.deadline == job.deadline
    assert final.timeout_seconds == 30
    assert final.max_actions == 7
    assert final.max_job_cost == UsdAmount(650_000)
    job.start_phase(now=now + timedelta(seconds=361))
    assert job.remaining_limits(now=now + timedelta(seconds=361)) is None


def test_starting_new_phase_does_not_reset_exhausted_actions_or_cost():
    now = datetime.now(UTC)
    for usage in (
        ExecutionUsage(total_actions=40),
        ExecutionUsage(total_actions=1, cost=UsdAmount(1_000_000)),
    ):
        job = context(now)
        job.deadline = now + timedelta(seconds=360)
        job.remaining_limits(now=now, inventory=True)
        job.consume(usage)
        job.start_phase(now=now + timedelta(seconds=100))
        assert job.remaining_limits(now=now + timedelta(seconds=100)) is None


def test_single_phase_operation_never_extends_past_original_180_seconds():
    now = datetime.now(UTC)
    job = context(now)
    first = job.remaining_limits(now=now)
    job.start_phase(now=now + timedelta(seconds=140))
    second = job.remaining_limits(now=now + timedelta(seconds=140))
    assert second.deadline == first.deadline == job.deadline
    assert second.timeout_seconds == 40
