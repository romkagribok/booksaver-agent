from dataclasses import replace
from datetime import timedelta

import pytest

from booksaver.application.inventory_executor import InventoryObservationValidator
from booksaver.domain.account_sync import InventoryCompleteness, ReservationLifecycle
from booksaver.domain.browser_executor import EvidenceCompleteness
from booksaver.domain.inventory_executor import (
    ActiveInventoryCoverage,
    ActiveInventoryRootExhaustion,
    InventoryExecutionResult,
    InventoryExecutionStatus,
    InventoryScope,
    ObservedReservation,
    TrustedInventoryCancellation,
)
from tests.unit.test_inventory_executor import NOW, _request, _reservation, _result


def _coverage(request=None, ids=frozenset({"ABC123"}), **changes):
    request = request or _request()
    return replace(ActiveInventoryCoverage(
        owner_user_id=request.owner_user_id, execution_id=request.execution_id,
        session_lease_id=request.session_lease.lease_id, active_confirmation_ids=ids,
        root_exhaustion=ActiveInventoryRootExhaustion.VERIFIED_TOTAL,
    ), **changes)


def _cancellation(request=None, confirmation="ABC123", **changes):
    request = request or _request()
    return replace(TrustedInventoryCancellation(
        owner_user_id=request.owner_user_id, execution_id=request.execution_id,
        session_lease_id=request.session_lease.lease_id, confirmation_id=confirmation,
    ), **changes)


def _cancelled(confirmation="ABC123"):
    return ObservedReservation(
        remote_id=confirmation, confirmation_id=confirmation,
        identity_evidence=EvidenceCompleteness.COMPLETE,
        lifecycle=ReservationLifecycle.CANCELLED, scope=InventoryScope.CANCELLED,
    )


def _validate(result, request=None):
    return InventoryObservationValidator(clock=lambda: NOW).validate(request or _request(), result)


def test_only_separate_bound_coverage_grants_active_scope_absence():
    model_only = _validate(_result())
    assert model_only.traversal_claim_complete
    assert model_only.to_discovery_result().completeness is InventoryCompleteness.INCOMPLETE
    accepted = _validate(replace(_result(), active_coverage=_coverage()))
    discovery = accepted.to_discovery_result()
    assert discovery.completeness is InventoryCompleteness.COMPLETE
    assert discovery.reconciliation_lifecycles == frozenset({
        ReservationLifecycle.UPCOMING, ReservationLifecycle.CURRENT,
    })
    assert discovery.reconciliation_user_id == 7
    assert discovery.failure_code is None


def test_explicit_empty_active_proof_can_complete_zero_positive_observations():
    result = replace(_result(reservations=()), active_coverage=_coverage(
        ids=frozenset(), root_exhaustion=ActiveInventoryRootExhaustion.EXPLICIT_EMPTY,
    ))
    discovery = _validate(result).to_discovery_result()
    assert discovery.completeness is InventoryCompleteness.COMPLETE
    assert discovery.observations == ()
    assert discovery.reconciliation_lifecycles is not None


@pytest.mark.parametrize("changes", [
    {"owner_user_id": 8}, {"execution_id": "other-execution"},
    {"session_lease_id": "other-lease"}, {"active_confirmation_ids": frozenset()},
    {"active_confirmation_ids": frozenset({"ABC123", "missing"})},
])
def test_wrong_binding_or_membership_preserves_positive_only_behavior(changes):
    validation = _validate(replace(_result(), active_coverage=_coverage(**changes)))
    assert validation.accepted_positive_count == 1
    assert validation.to_discovery_result().completeness is InventoryCompleteness.INCOMPLETE
    assert validation.to_discovery_result().reconciliation_lifecycles is None


@pytest.mark.parametrize("extra", [
    _reservation(remote_id="bad", confirmation_id="bad",
                 identity_evidence=EvidenceCompleteness.INCOMPLETE),
    _reservation(remote_id="other", confirmation_id="ABC123"),
    _reservation(remote_id="unknown", confirmation_id="unknown",
                 lifecycle=ReservationLifecycle.UNKNOWN),
    _reservation(remote_id="nodates", confirmation_id=None),
])
def test_rejected_ambiguous_or_unidentified_candidates_cannot_authorize_absence(extra):
    validation = _validate(replace(
        _result(reservations=(_reservation(), extra)), active_coverage=_coverage(),
    ))
    assert validation.to_discovery_result().completeness is InventoryCompleteness.INCOMPLETE


def test_conflicting_identity_rejects_all_authority():
    result = replace(_result(reservations=(
        _reservation(), _reservation(property_name="Conflicting property"),
    )), active_coverage=_coverage())
    discovery = _validate(result).to_discovery_result()
    assert discovery.completeness is InventoryCompleteness.FAILED
    assert not discovery.trusted_cancelled_confirmation_ids
    assert discovery.reconciliation_lifecycles is None


def test_expired_lease_cannot_authorize_absence():
    request = _request()
    request = replace(request, session_lease=replace(
        request.session_lease, expires_at=NOW - timedelta(seconds=1),
    ))
    validation = _validate(replace(_result(), active_coverage=_coverage(request)), request)
    assert not validation.complete_active_inventory


@pytest.mark.parametrize("status", [
    InventoryExecutionStatus.EMPTY_UPCOMING, InventoryExecutionStatus.SIGNED_OUT,
    InventoryExecutionStatus.UNSAFE_ACTION, InventoryExecutionStatus.TIMEOUT,
])
def test_non_observed_terminals_cannot_carry_coverage(status):
    with pytest.raises(ValueError, match="proof requires"):
        InventoryExecutionResult(status, active_coverage=_coverage(ids=frozenset()))


def test_cancellation_authority_requires_exact_validated_confirmation_and_binding():
    result = _result(reservations=(_cancelled(),))
    assert not _validate(result).to_discovery_result().trusted_cancelled_confirmation_ids
    result = replace(result, trusted_cancellations=(_cancellation(),))
    discovery = _validate(result).to_discovery_result()
    assert discovery.completeness is InventoryCompleteness.INCOMPLETE
    assert discovery.trusted_cancelled_confirmation_ids == frozenset({"ABC123"})
    assert discovery.reconciliation_user_id == 7
    assert discovery.observations[0].check_in is None
    for proof in (
        _cancellation(owner_user_id=8), _cancellation(execution_id="other"),
        _cancellation(session_lease_id="other"), _cancellation(confirmation="different"),
    ):
        invalid = replace(result, trusted_cancellations=(proof,))
        assert not _validate(invalid).to_discovery_result().trusted_cancelled_confirmation_ids


def test_active_and_cancelled_same_confirmation_cannot_grant_negative_authority():
    result = replace(_result(reservations=(_reservation(), _cancelled())),
                     active_coverage=_coverage(), trusted_cancellations=(_cancellation(),))
    validation = _validate(result)
    assert not validation.complete_active_inventory
    assert not validation.trusted_cancelled_confirmation_ids


def test_proof_repr_hides_confirmation_and_lease_identifiers():
    assert "ABC123" not in repr(_coverage())
    assert "inventory-lease-1" not in repr(_coverage())
    assert "ABC123" not in repr(_cancellation())
    with pytest.raises(ValueError, match="empty coverage"):
        _coverage(root_exhaustion=ActiveInventoryRootExhaustion.EXPLICIT_EMPTY)
    with pytest.raises(TypeError, match="recognized"):
        _coverage(root_exhaustion="model-says-complete")
