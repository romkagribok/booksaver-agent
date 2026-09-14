from __future__ import annotations

from dataclasses import replace
from datetime import timedelta

import pytest

from booksaver.application.browser_executor import ExecutionMeter, InMemorySessionLeaseBroker
from booksaver.application.inventory_executor import (
    InventoryExecutionService,
    InventoryObservationValidator,
    InventoryValidationFailure,
    OwnerBoundAgenticInventoryExecution,
)
from booksaver.domain.browser_executor import (
    MAX_COMPUTER_USE_ACTIONS,
    MAX_DAILY_COST_MICRO_USD,
    MAX_EXECUTOR_ACTIONS,
    MAX_JOB_COST_MICRO_USD,
    ExecutionLimits,
    ExecutionUsage,
)
from booksaver.domain.inventory_executor import MAX_INVENTORY_ACTIONS, InventoryExecutionLimits
from booksaver.domain.model_policy import UsdAmount
from tests.support.executors import FakeInventoryBrowserExecutor
from tests.unit.test_browser_executor import _request as _price_request
from tests.unit.test_inventory_executor import NOW, _request, _result


def test_inventory_has_distinct_action_cap_with_unchanged_common_caps() -> None:
    price = ExecutionLimits(deadline=NOW + timedelta(seconds=180))
    inventory = InventoryExecutionLimits(deadline=price.deadline)
    assert price.max_actions == MAX_EXECUTOR_ACTIONS == 15
    assert inventory.max_actions == MAX_INVENTORY_ACTIONS == 40
    assert inventory.deadline == price.deadline
    assert inventory.timeout_seconds == price.timeout_seconds == 180
    assert inventory.max_computer_use_actions == price.max_computer_use_actions
    assert inventory.max_job_cost == price.max_job_cost
    assert inventory.max_deployment_daily_cost == price.max_deployment_daily_cost
    with pytest.raises(ValueError, match="max_actions"):
        ExecutionLimits(deadline=price.deadline, max_actions=16)
    with pytest.raises(ValueError, match="max_actions"):
        InventoryExecutionLimits(deadline=price.deadline, max_actions=41)


@pytest.mark.parametrize(
    "updates",
    [
        {"max_actions": 0},
        {"max_computer_use_actions": MAX_COMPUTER_USE_ACTIONS + 1},
        {"max_actions": 2, "max_computer_use_actions": 3},
        {"timeout_seconds": 181},
        {"timeout_seconds": 0},
        {"max_job_cost": UsdAmount(MAX_JOB_COST_MICRO_USD + 1)},
        {"max_deployment_daily_cost": UsdAmount(MAX_DAILY_COST_MICRO_USD + 1)},
        {"deadline": NOW.replace(tzinfo=None)},
    ],
)
def test_inventory_cannot_relax_common_safety_caps(updates) -> None:
    with pytest.raises(ValueError):
        replace(InventoryExecutionLimits(deadline=NOW + timedelta(seconds=180)), **updates)


def test_price_request_rejects_larger_inventory_subclass_limit() -> None:
    limits = InventoryExecutionLimits(deadline=NOW + timedelta(seconds=180))
    with pytest.raises(ValueError, match="price execution"):
        _price_request(limits=limits)
    assert _request(limits=limits).limits is limits
    # Capability checks do not reject a genuinely lower shared residual allowance.
    lower = replace(limits, max_actions=12)
    assert _price_request(limits=lower).limits is lower


def test_existing_meter_enforces_inventory_action_boundary_without_extra_allowance() -> None:
    limits = InventoryExecutionLimits(deadline=NOW + timedelta(seconds=180))
    meter = ExecutionMeter(limits)
    for _ in range(40):
        meter.record_action()
    assert meter.snapshot().total_actions == 40
    with pytest.raises(RuntimeError, match="action limit"):
        meter.record_action()
    assert meter.snapshot().total_actions == 40


@pytest.mark.parametrize("count,accepted", [(15, True), (29, True), (40, True), (41, False)])
def test_inventory_validator_uses_capability_limit_for_observed_work(count, accepted) -> None:
    limits = InventoryExecutionLimits(deadline=NOW + timedelta(seconds=180))
    validation = InventoryObservationValidator(clock=lambda: NOW).validate(
        _request(limits=limits),
        _result(usage=ExecutionUsage(total_actions=count)),
    )
    if accepted:
        assert validation.failure is None
        assert validation.accepted_positive_count == 1
    else:
        assert validation.failure is InventoryValidationFailure.EXECUTION_LIMIT_BREACH
        assert validation.accepted_positive_count == 0


@pytest.mark.parametrize(
    "supplied",
    [
        None,
        ExecutionLimits(
            deadline=NOW + timedelta(seconds=37),
            max_actions=4,
            max_computer_use_actions=2,
            timeout_seconds=37,
            max_job_cost=UsdAmount(250_000),
        ),
    ],
)
def test_inventory_application_default_is_40_but_supplied_residual_is_never_expanded(
    supplied,
) -> None:
    broker = InMemorySessionLeaseBroker(clock=lambda: NOW)
    fake = FakeInventoryBrowserExecutor([_result()])
    execution = OwnerBoundAgenticInventoryExecution(
        InventoryExecutionService(fake, broker, InventoryObservationValidator(clock=lambda: NOW)),
        broker,
        clock=lambda: NOW,
    )
    execution.execute(owner_user_id=7, session_material=b"synthetic-unused", limits=supplied)
    issued = fake.requests[0].limits
    if supplied is None:
        assert isinstance(issued, InventoryExecutionLimits)
        assert issued.max_actions == 40
        assert issued.deadline == NOW + timedelta(seconds=180)
    else:
        assert issued is supplied
        assert issued.max_actions == 4
        assert issued.timeout_seconds == 37
        assert issued.max_job_cost == UsdAmount(250_000)
    assert broker.active_count() == 0
