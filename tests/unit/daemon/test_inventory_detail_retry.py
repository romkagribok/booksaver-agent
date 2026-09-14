import threading
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

from booksaver.application.inventory_executor import _to_reservation_observation
from booksaver.daemon.check_coordinator import ImmediateAdmission
from booksaver.domain.account_sync import (
    InventoryCompleteness,
    InventoryDiscoveryResult,
    SynchronizationTrigger,
)
from booksaver.domain.user import UserRole
from booksaver.infrastructure.persistence.sqlite_store import (
    SqliteAccountReservationRepository,
    SqliteStore,
    SqliteUserRepository,
)
from tests.support.executors import FakeInventoryBrowserExecutor
from tests.unit.daemon.test_check_coordinator import (
    BrowserContext,
    _agentic_inventory_result,
    _build_coordinator,
    _config,
    _future_booking,
    _observed_inventory_reservation,
    _seed_session,
    _session_repo,
)


def test_incomplete_saved_booking_retries_details_instead_of_identity_shortcut(
    tmp_path: Path,
) -> None:
    sessions = _session_repo(tmp_path)
    observed_at = datetime.now(UTC)
    complete = _to_reservation_observation(
        _observed_inventory_reservation(_future_booking("complete"), "complete"),
        observed_at,
    )
    partial = replace(
        _to_reservation_observation(
            _observed_inventory_reservation(_future_booking("partial"), "partial"),
            observed_at,
        ),
        property_ref=None,
        booked_total=None,
        occupancy=None,
        refundable=None,
    )
    with SqliteStore(tmp_path / "booksaver.db") as store:
        users = SqliteUserRepository(store)
        owner = users.get_owner()
        users.link_telegram_id(owner.user_id, 101)
        foreign = users.get_or_create_by_telegram_id(202, UserRole.USER)
        repository = SqliteAccountReservationRepository(store)
        for user_id, rows in ((owner.user_id, (complete, partial)), (foreign.user_id, (complete,))):
            repository.reconcile(
                user_id=user_id,
                run_id=f"seed-{user_id}",
                trigger=SynchronizationTrigger.BOOKINGS,
                session_revision="seed-session",
                result=InventoryDiscoveryResult(
                    observations=rows,
                    completeness=InventoryCompleteness.INCOMPLETE,
                ),
                observed_at=observed_at,
            )
        saved = repository.list_for_user(owner.user_id)
        assert sum(row.eligibility.is_eligible for row in saved) == 1
    _seed_session(sessions, owner.user_id)
    executor = FakeInventoryBrowserExecutor([_agentic_inventory_result()])
    coordinator = _build_coordinator(
        _config(tmp_path),
        browser_factory=BrowserContext,
        session_repository=sessions,
        agentic_inventory_executor_factory=lambda _budget, _leases: executor,
        bookings_inventory_executor_factory=lambda _budget, _leases: executor,
    )
    completed = threading.Event()
    assert (
        coordinator.request_inventory(101, lambda _outcome: completed.set())
        is ImmediateAdmission.ACCEPTED
    )
    assert completed.wait(2)
    request = executor.requests[0]
    assert request.owner_user_id == owner.user_id
    assert [row.confirmation_id for row in request.known_reservations] == [complete.confirmation_id]
    assert set(request.known_confirmation_ids) == {
        complete.confirmation_id,
        partial.confirmation_id,
    }
