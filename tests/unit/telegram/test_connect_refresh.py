from unittest.mock import Mock

import pytest

from booksaver.daemon.check_coordinator import ImmediateAdmission, InventoryCompletion
from booksaver.domain.account_sync import (
    InventoryCompleteness,
    SynchronizationFailureCode,
    SynchronizationReport,
    SynchronizationTrigger,
)
from booksaver.infrastructure.telegram.connect_refresh import start_post_connect_refresh


def report(completeness, *, count=1, failure=None):
    return SynchronizationReport(
        run_id="test-refresh",
        completeness=completeness,
        discovered=count,
        eligible=count,
        ineligible=0,
        failure_code=failure,
        failure_detail="INTERNAL DETAIL MUST NOT BE SHOWN",
    )


@pytest.mark.parametrize(
    "completeness", [InventoryCompleteness.COMPLETE, InventoryCompleteness.INCOMPLETE]
)
def test_fast_completion_is_after_progress_and_reports_success(completeness):
    coordinator = Mock()
    messages = []

    def immediate(user_id, callback, *, trigger):
        assert user_id == 42
        assert trigger is SynchronizationTrigger.CONNECT
        assert len(messages) == 1
        callback(InventoryCompletion(report(completeness)))
        return ImmediateAdmission.ACCEPTED

    coordinator.request_inventory.side_effect = immediate
    start_post_connect_refresh(42, coordinator, lambda user, text: messages.append((user, text)))
    assert len(messages) == 2
    assert "Loading your reservations" in messages[0][1]
    assert "Found 1 reservation." in messages[1][1]
    assert "check prices for 1" in messages[1][1]
    assert "Send /checknow" in messages[1][1]
    assert "retry" not in messages[1][1]
    assert "INTERNAL DETAIL" not in messages[1][1]
    assert ("Other saved reservations were kept" in messages[1][1]) is (
        completeness is InventoryCompleteness.INCOMPLETE
    )


@pytest.mark.parametrize(
    "result",
    [
        None,
        report(InventoryCompleteness.INCOMPLETE, count=0),
        report(
            InventoryCompleteness.FAILED, count=0,
            failure=SynchronizationFailureCode.NAVIGATION_FAILED,
        ),
        report(
            InventoryCompleteness.FAILED, count=0,
            failure=SynchronizationFailureCode.USER_KEY_INVALID,
        ),
        report(
            InventoryCompleteness.INCOMPLETE,
            failure=SynchronizationFailureCode.EXTRACTION_AMBIGUOUS,
        ),
        report(
            InventoryCompleteness.FAILED, count=0, failure=SynchronizationFailureCode.AUTH_REQUIRED
        ),
    ],
)
def test_incomplete_or_failed_refresh_is_not_mislabeled_success(result):
    coordinator = Mock()
    coordinator.request_inventory.return_value = ImmediateAdmission.ACCEPTED
    messages = []
    start_post_connect_refresh(42, coordinator, lambda _, text: messages.append(text))
    callback = coordinator.request_inventory.call_args.args[1]
    callback(InventoryCompletion(result))
    assert "couldn't load your reservations" in messages[-1]
    code = result.failure_code if result is not None else None
    if code is SynchronizationFailureCode.AUTH_REQUIRED:
        assert "Send /connect" in messages[-1]
    elif code is SynchronizationFailureCode.USER_KEY_INVALID:
        assert "/setkey" in messages[-1]
        assert "/deletekey" in messages[-1]
    else:
        assert "Try /bookings" in messages[-1]
        assert "/connect" not in messages[-1]
    if code is not None:
        assert code.value not in messages[-1]
    assert "INTERNAL DETAIL" not in messages[-1]
    assert "Send /checknow" not in messages[-1]


@pytest.mark.parametrize(
    "admission, expected",
    [
        (ImmediateAdmission.BUSY, "haven't loaded your reservations"),
        (ImmediateAdmission.STOPPING, "shutting down"),
    ],
)
def test_declined_refresh_describes_actual_admission(admission, expected):
    coordinator = Mock()
    coordinator.request_inventory.return_value = admission
    messages = []
    start_post_connect_refresh(42, coordinator, lambda _, text: messages.append(text))
    assert len(messages) == 2
    assert expected in messages[-1]
    coordinator.request_inventory.assert_called_once()


def test_explicit_empty_account_does_not_report_failure_or_request_price_check():
    coordinator = Mock()
    coordinator.request_inventory.return_value = ImmediateAdmission.ACCEPTED
    messages = []
    start_post_connect_refresh(42, coordinator, lambda _, text: messages.append(text))
    callback = coordinator.request_inventory.call_args.args[1]
    callback(InventoryCompletion(SynchronizationReport(
        run_id="empty", completeness=InventoryCompleteness.INCOMPLETE,
        discovered=0, eligible=0, ineligible=0, upcoming_empty_observed=True,
    )))
    assert "did not find upcoming hotel reservations in the trips we checked" in messages[-1]
    assert "check which Booking.com account" in messages[-1]
    assert "couldn't" not in messages[-1]
    assert "/checknow" not in messages[-1]
    assert "/connect" not in messages[-1]
