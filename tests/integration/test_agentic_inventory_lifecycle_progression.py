from dataclasses import replace
from datetime import UTC, date, datetime, timedelta, timezone
from decimal import Decimal

import pytest

from booksaver.domain.account_sync import (
    InventoryCompleteness,
    InventoryDiscoveryResult,
    ReservationLifecycle,
    ReservationObservation,
    SynchronizationFailureCode,
    SynchronizationTrigger,
)
from booksaver.domain.value_objects import Money, Occupancy
from booksaver.infrastructure.persistence.sqlite_store import (
    SqliteAccountReservationRepository,
    SqliteBookingRepository,
    SqliteStore,
    SqliteUserRepository,
)

SEED = datetime(2026, 9, 1, tzinfo=UTC)
NOW = datetime(2026, 9, 13, 20, tzinfo=UTC)


def _reservation():
    return ReservationObservation(
        remote_id="internal-original", confirmation_id="1234567890",
        lifecycle=ReservationLifecycle.UPCOMING, observed_at=SEED,
        property_name="Synthetic Hotel",
        property_ref="https://www.booking.com/hotel/de/synthetic-hotel.html",
        check_in=date(2026, 9, 11), check_out=date(2026, 9, 14),
        room_type="Twin Room", booked_total=Money(Decimal("300"), "EUR"),
        refundable=True, refund_note="Free cancellation", refund_deadline=date(2026, 9, 10),
        occupancy=Occupancy(2, 0, 1), extraction_method="dom",
    )


def _sync(repo, user_id, run_id, observations, *, now=NOW):
    return repo.reconcile(
        user_id=user_id, run_id=run_id, trigger=SynchronizationTrigger.BOOKINGS,
        session_revision="caller-session", observed_at=now,
        result=InventoryDiscoveryResult(tuple(observations), InventoryCompleteness.INCOMPLETE),
    )


@pytest.fixture
def state(tmp_path):
    with SqliteStore(tmp_path / "state.db") as store:
        user_id = SqliteUserRepository(store).get_owner().user_id
        repo = SqliteAccountReservationRepository(store)
        _sync(repo, user_id, "seed", [_reservation()], now=SEED)
        yield store, repo, user_id


def test_current_saved_stay_and_unrelated_future_positive_commit_together(state):
    store, repo, user_id = state
    before = repo.list_for_user(user_id)[0]
    current = replace(
        _reservation(), remote_id="1234567890", lifecycle=ReservationLifecycle.CURRENT,
        observed_at=NOW, extraction_method="agentic_inventory",
    )
    future = replace(
        _reservation(), remote_id="new-remote", confirmation_id="9988776655",
        check_in=date(2026, 10, 11), check_out=date(2026, 10, 14),
        observed_at=NOW, extraction_method="agentic_inventory",
    )
    report = _sync(repo, user_id, "mixed", [future, current])
    assert report.completeness is InventoryCompleteness.INCOMPLETE
    assert report.failure_code is None
    assert (report.discovered, report.eligible, report.ineligible) == (2, 1, 1)
    rows = repo.list_for_user(user_id)
    after = next(row for row in rows if row.observation.confirmation_id == current.confirmation_id)
    assert after.account_reservation_id == before.account_reservation_id
    assert after.observation.lifecycle is ReservationLifecycle.CURRENT
    assert after.snapshot_revision == before.snapshot_revision + 1
    assert not after.eligibility.is_eligible
    assert after.observation.booked_total == before.observation.booked_total
    assert after.observation.refundable == before.observation.refundable
    assert after.observation.refund_deadline == before.observation.refund_deadline
    assert after.observation.occupancy == before.observation.occupancy
    assert after.monitoring_booking_id == before.monitoring_booking_id
    active = SqliteBookingRepository(store).list_active_for_user(user_id)
    assert len(active) == 1
    assert active[0].booking_id != before.monitoring_booking_id
    assert repo.positively_observed_booking_ids_for_run(user_id=user_id, run_id="mixed") == (
        active[0].booking_id,
    )
    assert repo.latest_run_for_user(user_id) == report


@pytest.mark.parametrize("starting,ending,now", [
    (ReservationLifecycle.UPCOMING, ReservationLifecycle.CURRENT, NOW),
    (ReservationLifecycle.UPCOMING, ReservationLifecycle.COMPLETED,
     datetime(2026, 9, 14, tzinfo=UTC)),
    (ReservationLifecycle.CURRENT, ReservationLifecycle.COMPLETED,
     datetime(2026, 9, 14, tzinfo=UTC)),
])
def test_only_date_proven_forward_lifecycle_progression_is_accepted(state, starting, ending, now):
    store, repo, user_id = state
    if starting is ReservationLifecycle.CURRENT:
        _sync(repo, user_id, "seed-current", [replace(_reservation(), lifecycle=starting)])
    incoming = replace(_reservation(), lifecycle=ending, extraction_method="agentic_inventory")
    report = _sync(repo, user_id, "forward", [incoming], now=now)
    assert report.failure_code is None
    assert report.eligible == 0
    assert repo.list_for_user(user_id)[0].observation.lifecycle is ending
    assert SqliteBookingRepository(store).list_active_for_user(user_id) == []
    assert repo.positively_observed_booking_ids_for_run(user_id=user_id, run_id="forward") == ()


@pytest.mark.parametrize("changes", [
    {"confirmation_id": None}, {"confirmation_id": "different"},
    {"check_in": None}, {"check_out": None}, {"check_in": date(2026, 9, 12)},
    {"check_out": date(2026, 9, 15)},
    {"property_name": "Different Hotel", "property_ref": None},
    {"property_ref": "different"},
    {"property_ref": "https://www.booking.com/hotel/de/different-hotel.en-us.html"},
    {"property_ref": "https://www.booking.com/hotel/de/synthetic-hotel.html/"},
    {"room_type": "Different Room"},
    {"booked_total": Money(Decimal("299"), "EUR")},
    {"booked_total": Money(Decimal("300"), "USD")}, {"refundable": False},
    {"refund_deadline": date(2026, 9, 9)}, {"occupancy": Occupancy(1, 0, 1)},
    {"lifecycle": ReservationLifecycle.CANCELLED},
])
def test_lifecycle_progression_never_waives_other_explicit_conflicts(state, changes):
    store, repo, user_id = state
    before = repo.list_for_user(user_id)
    incoming = replace(
        _reservation(), lifecycle=ReservationLifecycle.CURRENT,
        extraction_method="agentic_inventory",
    )
    incoming = replace(incoming, **changes)
    report = _sync(repo, user_id, "reject", [incoming])
    assert report.completeness is InventoryCompleteness.FAILED
    assert report.failure_code is SynchronizationFailureCode.PERSISTENCE_CONFLICT
    assert repo.list_for_user(user_id) == before
    assert len(SqliteBookingRepository(store).list_active_for_user(user_id)) == 1
    assert repo.positively_observed_booking_ids_for_run(user_id=user_id, run_id="reject") == ()


@pytest.mark.parametrize("lifecycle,now", [
    (ReservationLifecycle.CURRENT, SEED),
    (ReservationLifecycle.CURRENT, datetime(2026, 9, 14, tzinfo=UTC)),
    (ReservationLifecycle.COMPLETED, NOW),
    (ReservationLifecycle.CURRENT, NOW.replace(tzinfo=None)),
    # Trusted UTC is still Sep 10, despite the local Sep 11 date.
    (ReservationLifecycle.CURRENT, datetime(2026, 9, 11, tzinfo=timezone(timedelta(hours=14)))),
])
def test_premature_or_inconsistent_status_uses_trusted_utc_clock(state, lifecycle, now):
    _, repo, user_id = state
    before = repo.list_for_user(user_id)
    incoming = replace(
        _reservation(), lifecycle=lifecycle, extraction_method="agentic_inventory",
        observed_at=datetime(2027, 1, 1, tzinfo=UTC),
    )
    report = _sync(repo, user_id, "bad-date", [incoming], now=now)
    assert report.failure_code is SynchronizationFailureCode.PERSISTENCE_CONFLICT
    assert repo.list_for_user(user_id) == before


@pytest.mark.parametrize("starting,ending", [
    (ReservationLifecycle.CURRENT, ReservationLifecycle.UPCOMING),
    (ReservationLifecycle.COMPLETED, ReservationLifecycle.CURRENT),
    (ReservationLifecycle.COMPLETED, ReservationLifecycle.UPCOMING),
    (ReservationLifecycle.CANCELLED, ReservationLifecycle.CURRENT),
])
def test_backward_or_cancelled_lifecycle_changes_remain_conflicts(state, starting, ending):
    _, repo, user_id = state
    _sync(repo, user_id, "seed-status", [replace(_reservation(), lifecycle=starting)])
    before = repo.list_for_user(user_id)
    incoming = replace(_reservation(), lifecycle=ending, extraction_method="agentic_inventory")
    report = _sync(repo, user_id, "backward", [incoming])
    assert report.failure_code is SynchronizationFailureCode.PERSISTENCE_CONFLICT
    assert repo.list_for_user(user_id) == before


def test_same_confirmation_in_another_callers_account_is_untouched(state):
    store, repo, owner_id = state
    invitee = SqliteUserRepository(store).get_or_create_by_telegram_id(445566)
    _sync(repo, invitee.user_id, "seed-invitee", [_reservation()], now=SEED)
    owner_before = repo.list_for_user(owner_id)
    current = replace(
        _reservation(), lifecycle=ReservationLifecycle.CURRENT,
        extraction_method="agentic_inventory",
    )
    report = _sync(repo, invitee.user_id, "invitee-current", [current])
    assert report.failure_code is None
    assert repo.list_for_user(owner_id) == owner_before
    assert repo.list_for_user(invitee.user_id)[0].observation.lifecycle is (
        ReservationLifecycle.CURRENT
    )
    assert repo.positively_observed_booking_ids_for_run(
        user_id=owner_id, run_id="invitee-current",
    ) == ()


@pytest.mark.parametrize("missing", ["confirmation_id", "check_in", "check_out"])
def test_forward_progress_requires_explicit_matching_saved_identity_and_dates(state, missing):
    _, repo, user_id = state
    _sync(repo, user_id, "seed-missing", [replace(_reservation(), **{missing: None})])
    before = repo.list_for_user(user_id)
    incoming = replace(
        _reservation(), lifecycle=ReservationLifecycle.CURRENT,
        extraction_method="agentic_inventory",
    )
    report = _sync(repo, user_id, "missing", [incoming])
    assert report.failure_code is SynchronizationFailureCode.PERSISTENCE_CONFLICT
    assert repo.list_for_user(user_id) == before


def test_real_fact_conflict_still_rolls_back_unrelated_positive(state):
    _, repo, user_id = state
    before = repo.list_for_user(user_id)
    fresh = replace(
        _reservation(), remote_id="fresh", confirmation_id="8877665544",
        check_in=date(2026, 10, 11), check_out=date(2026, 10, 14),
        extraction_method="agentic_inventory",
    )
    conflicting = replace(
        _reservation(), lifecycle=ReservationLifecycle.CURRENT,
        booked_total=Money(Decimal("250"), "EUR"), extraction_method="agentic_inventory",
    )
    report = _sync(repo, user_id, "atomic-conflict", [fresh, conflicting])
    assert report.failure_code is SynchronizationFailureCode.PERSISTENCE_CONFLICT
    assert repo.list_for_user(user_id) == before
    assert repo.positively_observed_booking_ids_for_run(
        user_id=user_id, run_id="atomic-conflict",
    ) == ()


def test_current_progress_uses_utc_day_when_local_date_has_reached_checkout(state):
    _, repo, user_id = state
    incoming = replace(
        _reservation(), lifecycle=ReservationLifecycle.CURRENT,
        extraction_method="agentic_inventory",
    )
    local_checkout = datetime(2026, 9, 14, tzinfo=timezone(timedelta(hours=14)))
    report = _sync(repo, user_id, "utc-current", [incoming], now=local_checkout)
    assert report.failure_code is None
    assert repo.list_for_user(user_id)[0].observation.lifecycle is ReservationLifecycle.CURRENT
