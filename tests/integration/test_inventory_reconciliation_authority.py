from dataclasses import replace
from decimal import Decimal

import pytest

from booksaver.application.inventory_executor import InventoryObservationValidator
from booksaver.domain.account_sync import (
    InventoryCompleteness,
    InventoryDiscoveryResult,
    ReservationLifecycle,
    SynchronizationFailureCode,
    SynchronizationTrigger,
)
from booksaver.domain.browser_executor import AllInEvidence
from booksaver.domain.value_objects import Money
from booksaver.infrastructure.persistence.sqlite_store import (
    SqliteAccountReservationRepository,
    SqliteBookingRepository,
    SqliteStore,
    SqliteUserRepository,
)
from tests.unit.test_inventory_executor import NOW, _request, _reservation, _result
from tests.unit.test_inventory_reconciliation_authority import _cancellation, _cancelled, _coverage


def request_for(user_id):
    base = _request()
    return replace(base, owner_user_id=user_id, session_lease=replace(
        base.session_lease, owner_user_id=user_id, subject_id=f"account:{user_id}",
    ))


def discovery(user_id, observations=(), *, complete=False, cancellations=()):
    request = request_for(user_id)
    result = _result(reservations=tuple(observations))
    result = replace(
        result,
        active_coverage=_coverage(request, ids=frozenset(
            item.confirmation_id for item in observations
            if item.lifecycle in {ReservationLifecycle.UPCOMING, ReservationLifecycle.CURRENT}
        )) if complete else None,
        trusted_cancellations=tuple(_cancellation(request, item) for item in cancellations),
    )
    return InventoryObservationValidator(clock=lambda: NOW).validate(
        request, result,
    ).to_discovery_result()


def sync(repo, user_id, run_id, result):
    return repo.reconcile(
        user_id=user_id, run_id=run_id, trigger=SynchronizationTrigger.BOOKINGS,
        session_revision="caller-revision", observed_at=NOW, result=result,
    )


def seed(repo, user_id, run_id="seed", observations=None):
    return sync(repo, user_id, run_id, discovery(
        user_id, observations if observations is not None else (_reservation(),),
    ))


def add_savings(store, booking_id):
    store.conn.execute(
        "INSERT INTO savings_opportunities (opportunity_id, booking_id, check_id, "
        "baseline_amount, live_amount, currency, amount_saved, percent_saved, validated_at) "
        "VALUES ('test-opportunity', ?, 'test-check', '301', '250', 'USD', '51', '16.94', ?)",
        (booking_id, NOW.isoformat()),
    )
    store.conn.commit()


@pytest.fixture
def state(tmp_path):
    with SqliteStore(tmp_path / "state.db") as store:
        user_id = SqliteUserRepository(store).get_owner().user_id
        repo = SqliteAccountReservationRepository(store)
        seed(repo, user_id)
        yield store, repo, user_id


def test_empty_trusted_active_scope_archives_projection_and_savings_atomically(state):
    store, repo, user_id = state
    before = repo.list_for_user(user_id)[0]
    add_savings(store, before.monitoring_booking_id)
    report = sync(repo, user_id, "active-empty", discovery(user_id, complete=True))
    assert report.completeness is InventoryCompleteness.COMPLETE
    after = repo.list_for_user(user_id)[0]
    assert after.observation.lifecycle is ReservationLifecycle.ABSENT
    assert after.last_sync_run_id == report.run_id
    assert after.observation.booked_total == before.observation.booked_total
    assert after.observation.refund_deadline == before.observation.refund_deadline
    assert after.monitoring_booking_id == before.monitoring_booking_id
    assert not SqliteBookingRepository(store).list_active_for_user(user_id)
    assert store.conn.execute("SELECT COUNT(*) FROM savings_opportunities").fetchone()[0] == 0
    assert not repo.positively_observed_booking_ids_for_run(user_id=user_id, run_id=report.run_id)


def test_active_scope_does_not_rewrite_saved_inactive_or_unknown_rows(state):
    _, repo, user_id = state
    for lifecycle in (ReservationLifecycle.CANCELLED, ReservationLifecycle.COMPLETED,
                      ReservationLifecycle.UNKNOWN, ReservationLifecycle.CURRENT):
        observation = replace(discovery(user_id, (_reservation(),)).observations[0],
                              remote_id=lifecycle.value, confirmation_id=lifecycle.value,
                              lifecycle=lifecycle, extraction_method="dom")
        sync(repo, user_id, lifecycle.value, InventoryDiscoveryResult(
            (observation,), InventoryCompleteness.INCOMPLETE,
        ))
    before = {r.observation.confirmation_id: r for r in repo.list_for_user(user_id)}
    sync(repo, user_id, "active-empty", discovery(user_id, complete=True))
    after = {r.observation.confirmation_id: r for r in repo.list_for_user(user_id)}
    for lifecycle in (ReservationLifecycle.CANCELLED, ReservationLifecycle.COMPLETED,
                      ReservationLifecycle.UNKNOWN):
        assert after[lifecycle.value] == before[lifecycle.value]
    assert after["current"].observation.lifecycle is ReservationLifecycle.ABSENT
    assert after["ABC123"].observation.lifecycle is ReservationLifecycle.ABSENT


def test_incomplete_model_claims_preserve_saved_state_and_old_run_id(state):
    _, repo, user_id = state
    before = repo.list_for_user(user_id)
    report = sync(repo, user_id, "model-empty", discovery(user_id))
    assert report.completeness is InventoryCompleteness.INCOMPLETE
    assert repo.list_for_user(user_id) == before
    assert before[0].last_sync_run_id == "seed"


def test_absent_reservation_can_reappear_without_changing_baseline_or_identity(state):
    store, repo, user_id = state
    before = repo.list_for_user(user_id)[0]
    sync(repo, user_id, "absent", discovery(user_id, complete=True))
    report = seed(repo, user_id, "reappeared")
    assert report.failure_code is None
    after = repo.list_for_user(user_id)[0]
    assert after.account_reservation_id == before.account_reservation_id
    assert after.observation.lifecycle is ReservationLifecycle.UPCOMING
    assert after.monitoring_booking_id == before.monitoring_booking_id
    assert after.observation.booked_total == before.observation.booked_total
    assert len(SqliteBookingRepository(store).list_active_for_user(user_id)) == 1
    assert repo.positively_observed_booking_ids_for_run(user_id=user_id, run_id="reappeared") == (
        before.monitoring_booking_id,
    )


def test_explicit_cancellation_without_dates_preserves_finance_and_retires_exact_identity(state):
    store, repo, user_id = state
    before = repo.list_for_user(user_id)[0]
    add_savings(store, before.monitoring_booking_id)
    report = sync(repo, user_id, "cancelled", discovery(
        user_id, (_cancelled(),), cancellations=("ABC123",),
    ))
    assert report.failure_code is None
    assert report.completeness is InventoryCompleteness.INCOMPLETE
    assert report.eligible == 0
    after = repo.list_for_user(user_id)[0]
    assert after.observation.lifecycle is ReservationLifecycle.CANCELLED
    assert after.observation.booked_total == before.observation.booked_total
    assert after.observation.check_in == before.observation.check_in
    assert after.observation.refund_deadline == before.observation.refund_deadline
    assert after.observation.occupancy == before.observation.occupancy
    assert after.monitoring_booking_id == before.monitoring_booking_id
    assert not SqliteBookingRepository(store).list_active_for_user(user_id)
    assert not repo.positively_observed_booking_ids_for_run(user_id=user_id, run_id="cancelled")
    assert store.conn.execute("SELECT COUNT(*) FROM savings_opportunities").fetchone()[0] == 0


def test_model_only_cancellation_still_conflicts(state):
    _, repo, user_id = state
    before = repo.list_for_user(user_id)
    report = sync(repo, user_id, "model-cancel", discovery(user_id, (_cancelled(),)))
    assert report.failure_code is SynchronizationFailureCode.PERSISTENCE_CONFLICT
    assert repo.list_for_user(user_id) == before


def test_cancellation_and_new_booking_at_same_hotel_remain_distinct(state):
    _, repo, user_id = state
    original = repo.list_for_user(user_id)[0]
    new = _reservation(remote_id="new-trip", confirmation_id="NEW123")
    report = sync(repo, user_id, "rebooked", discovery(
        user_id, (_cancelled(), new), complete=True, cancellations=("ABC123",),
    ))
    assert report.failure_code is None
    rows = {r.observation.confirmation_id: r for r in repo.list_for_user(user_id)}
    assert len(rows) == 2
    assert rows["ABC123"].account_reservation_id == original.account_reservation_id
    assert rows["ABC123"].observation.lifecycle is ReservationLifecycle.CANCELLED
    assert rows["NEW123"].observation.lifecycle is ReservationLifecycle.UPCOMING
    assert rows["NEW123"].monitoring_booking_id != original.monitoring_booking_id


@pytest.mark.parametrize("kind", ["absence", "cancellation"])
def test_negative_authority_cannot_cross_caller_boundary(state, kind):
    store, repo, owner_id = state
    invitee = SqliteUserRepository(store).get_or_create_by_telegram_id(887766)
    seed(repo, invitee.user_id, "invitee-seed")
    before_owner = repo.list_for_user(owner_id)
    before_invitee = repo.list_for_user(invitee.user_id)
    result = discovery(owner_id, complete=True) if kind == "absence" else discovery(
        owner_id, (_cancelled(),), cancellations=("ABC123",),
    )
    report = sync(repo, invitee.user_id, "wrong-caller", result)
    assert report.failure_code is SynchronizationFailureCode.PERSISTENCE_CONFLICT
    assert repo.list_for_user(owner_id) == before_owner
    assert repo.list_for_user(invitee.user_id) == before_invitee
    valid = discovery(invitee.user_id, complete=True) if kind == "absence" else discovery(
        invitee.user_id, (_cancelled(),), cancellations=("ABC123",),
    )
    assert sync(repo, invitee.user_id, "correct-caller", valid).failure_code is None
    assert repo.list_for_user(owner_id) == before_owner


@pytest.mark.parametrize("change", [
    {"property_name": "Another Hotel"},
    {"booked_total": Money(Decimal("299"), "USD"), "all_in": AllInEvidence.EXPLICIT},
    {"confirmation_id": "different", "remote_id": "trip-123"},
])
def test_trusted_cancellation_does_not_waive_identity_or_financial_conflicts(state, change):
    store, repo, user_id = state
    before = repo.list_for_user(user_id)
    add_savings(store, before[0].monitoring_booking_id)
    changed = replace(_cancelled(), **change)
    new = _reservation(remote_id="new", confirmation_id="NEW123")
    report = sync(repo, user_id, "conflict", discovery(
        user_id, (new, changed), complete=True, cancellations=(changed.confirmation_id,),
    ))
    assert report.failure_code is SynchronizationFailureCode.PERSISTENCE_CONFLICT
    assert repo.list_for_user(user_id) == before
    assert store.conn.execute("SELECT COUNT(*) FROM savings_opportunities").fetchone()[0] == 1
    assert not repo.positively_observed_booking_ids_for_run(user_id=user_id, run_id="conflict")


def test_legacy_complete_reconciliation_still_covers_all_lifecycles(state):
    _, repo, user_id = state
    cancelled = replace(discovery(user_id, (_reservation(),)).observations[0],
                        lifecycle=ReservationLifecycle.CANCELLED, extraction_method="dom")
    sync(repo, user_id, "legacy-cancel", InventoryDiscoveryResult(
        (cancelled,), InventoryCompleteness.INCOMPLETE,
    ))
    sync(repo, user_id, "legacy-complete", InventoryDiscoveryResult(
        (), InventoryCompleteness.COMPLETE,
    ))
    assert repo.list_for_user(user_id)[0].observation.lifecycle is ReservationLifecycle.ABSENT
