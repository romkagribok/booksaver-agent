from dataclasses import replace
from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from booksaver.domain.account_sync import (
    EligibilityReason,
    InventoryCompleteness,
    InventoryDiscoveryResult,
    ReservationLifecycle,
    ReservationObservation,
    SynchronizationFailureCode,
    SynchronizationTrigger,
)
from booksaver.domain.user import UserAccessState
from booksaver.domain.value_objects import Money, Occupancy
from booksaver.infrastructure.persistence.sqlite_store import (
    SqliteAccountReservationRepository,
    SqliteBookingRepository,
    SqliteStore,
    SqliteUserRepository,
)

NOW = datetime(2026, 7, 27, tzinfo=UTC)


def _eligible(remote_id: str = "remote-1") -> ReservationObservation:
    return ReservationObservation(
        remote_id=remote_id,
        lifecycle=ReservationLifecycle.UPCOMING,
        observed_at=NOW,
        confirmation_id=f"CONF-{remote_id}",
        property_name="Hotel Example",
        property_ref="hotel-example",
        check_in=date(2027, 1, 10),
        check_out=date(2027, 1, 12),
        room_type="King room",
        booked_total=Money.of("200", "USD"),
        refundable=True,
        occupancy=Occupancy(2, 0, 1),
    )


def _reconcile(
    repo: SqliteAccountReservationRepository,
    user_id: int,
    run_id: str,
    result: InventoryDiscoveryResult,
) -> None:
    repo.reconcile(
        user_id=user_id,
        run_id=run_id,
        trigger=SynchronizationTrigger.BOOKINGS,
        session_revision="session-1",
        result=result,
        observed_at=NOW,
    )


def test_complete_reconciliation_projects_only_eligible_reservations(
    tmp_path: Path,
) -> None:
    with SqliteStore(tmp_path / "booksaver.db") as store:
        user = SqliteUserRepository(store).get_owner()
        repo = SqliteAccountReservationRepository(store)
        ineligible = ReservationObservation(
            remote_id="remote-2",
            lifecycle=ReservationLifecycle.CANCELLED,
            observed_at=NOW,
            property_name="Cancelled Hotel",
        )

        _reconcile(
            repo,
            user.user_id,
            "run-1",
            InventoryDiscoveryResult(
                (_eligible(), ineligible), InventoryCompleteness.COMPLETE
            ),
        )

        inventory = repo.list_for_user(user.user_id)
        projected = SqliteBookingRepository(store).list_active_for_user(user.user_id)

    assert len(inventory) == 2
    assert len(projected) == 1
    assert inventory[1].eligibility.reasons


def test_only_complete_run_marks_unseen_reservation_absent(tmp_path: Path) -> None:
    with SqliteStore(tmp_path / "booksaver.db") as store:
        user = SqliteUserRepository(store).get_owner()
        repo = SqliteAccountReservationRepository(store)
        _reconcile(
            repo,
            user.user_id,
            "run-1",
            InventoryDiscoveryResult((_eligible(),), InventoryCompleteness.COMPLETE),
        )
        _reconcile(
            repo,
            user.user_id,
            "run-2",
            InventoryDiscoveryResult((), InventoryCompleteness.INCOMPLETE),
        )
        assert repo.list_for_user(user.user_id)[0].eligibility.is_eligible

        _reconcile(
            repo,
            user.user_id,
            "run-3",
            InventoryDiscoveryResult((), InventoryCompleteness.COMPLETE),
        )
        reservation = repo.list_for_user(user.user_id)[0]

        assert reservation.observation.lifecycle is ReservationLifecycle.ABSENT
        assert reservation.eligibility.reasons == (EligibilityReason.NOT_OBSERVED,)
        assert SqliteBookingRepository(store).list_active_for_user(user.user_id) == []


def test_failed_run_preserves_last_confirmed_inventory(tmp_path: Path) -> None:
    with SqliteStore(tmp_path / "booksaver.db") as store:
        user = SqliteUserRepository(store).get_owner()
        repo = SqliteAccountReservationRepository(store)
        _reconcile(
            repo,
            user.user_id,
            "run-1",
            InventoryDiscoveryResult((_eligible(),), InventoryCompleteness.COMPLETE),
        )
        _reconcile(
            repo,
            user.user_id,
            "run-2",
            InventoryDiscoveryResult.failed(
                SynchronizationFailureCode.NAVIGATION_FAILED,
                "Inventory unavailable.",
            ),
        )

        assert repo.list_for_user(user.user_id)[0].eligibility.is_eligible
        assert repo.latest_run_for_user(user.user_id).failure_code is (
            SynchronizationFailureCode.NAVIGATION_FAILED
        )


def test_same_remote_identity_is_isolated_per_user(tmp_path: Path) -> None:
    with SqliteStore(tmp_path / "booksaver.db") as store:
        users = SqliteUserRepository(store)
        owner = users.get_owner()
        other = users.get_or_create_by_telegram_id(222)
        repo = SqliteAccountReservationRepository(store)

        for run_id, user_id in (("run-owner", owner.user_id), ("run-user", other.user_id)):
            _reconcile(
                repo,
                user_id,
                run_id,
                InventoryDiscoveryResult((_eligible(),), InventoryCompleteness.COMPLETE),
            )

        assert len(repo.list_for_user(owner.user_id)) == 1
        assert len(repo.list_for_user(other.user_id)) == 1
        assert (
            repo.list_for_user(owner.user_id)[0].remote_key_hash
            != repo.list_for_user(other.user_id)[0].remote_key_hash
        )


def test_user_purge_removes_inventory_runs_and_projection(tmp_path: Path) -> None:
    with SqliteStore(tmp_path / "booksaver.db") as store:
        users = SqliteUserRepository(store)
        user = users.get_or_create_by_telegram_id(222)
        repo = SqliteAccountReservationRepository(store)
        _reconcile(
            repo,
            user.user_id,
            "run-purge",
            InventoryDiscoveryResult((_eligible(),), InventoryCompleteness.COMPLETE),
        )

        users.purge(user.user_id)

        assert users.get_by_id(user.user_id) is None
        assert repo.list_for_user(user.user_id) == []
        assert repo.latest_run_for_user(user.user_id) is None
        assert store.conn.execute(
            "SELECT COUNT(*) FROM bookings WHERE user_id = ?", (user.user_id,)
        ).fetchone()[0] == 0


def test_reconciliation_rechecks_active_access_inside_transaction(
    tmp_path: Path,
) -> None:
    with SqliteStore(tmp_path / "booksaver.db") as store:
        users = SqliteUserRepository(store)
        user = users.get_or_create_by_telegram_id(222)
        users.set_access_state(user.user_id, UserAccessState.REVOKED)

        with pytest.raises(PermissionError, match="no longer an active"):
            _reconcile(
                SqliteAccountReservationRepository(store),
                user.user_id,
                "run-revoked",
                InventoryDiscoveryResult((_eligible(),), InventoryCompleteness.COMPLETE),
            )

        assert store.conn.execute(
            "SELECT COUNT(*) FROM booking_sync_runs WHERE user_id = ?",
            (user.user_id,),
        ).fetchone()[0] == 0


def test_projection_identity_conflict_rolls_back_and_records_failed_run(
    tmp_path: Path,
) -> None:
    with SqliteStore(tmp_path / "booksaver.db") as store:
        user = SqliteUserRepository(store).get_owner()
        first = replace(_eligible("remote-1"), confirmation_id="SAME-CONF")
        second = replace(_eligible("remote-2"), confirmation_id="SAME-CONF")
        repo = SqliteAccountReservationRepository(store)

        report = repo.reconcile(
            user_id=user.user_id,
            run_id="run-conflict",
            trigger=SynchronizationTrigger.BOOKINGS,
            session_revision="session-1",
            result=InventoryDiscoveryResult(
                (first, second), InventoryCompleteness.COMPLETE
            ),
            observed_at=NOW,
        )

        assert report.failure_code is SynchronizationFailureCode.PERSISTENCE_CONFLICT
        assert repo.list_for_user(user.user_id) == []
        assert SqliteBookingRepository(store).list_all_for_user(user.user_id) == []
        assert repo.latest_run_for_user(user.user_id) == report
