from __future__ import annotations

from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

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
    SCHEMA_VERSION,
    InventoryExecutionMetrics,
    SqliteAccountReservationRepository,
    SqliteInventoryExecutionMetricsRepository,
    SqliteStore,
    SqliteUserRepository,
)

NOW = datetime(2026, 8, 25, tzinfo=UTC)


def _create_sync_run(store: SqliteStore, *, run_id: str = "inventory-run-1") -> int:
    owner = SqliteUserRepository(store).get_owner()
    SqliteAccountReservationRepository(store).reconcile(
        user_id=owner.user_id,
        run_id=run_id,
        trigger=SynchronizationTrigger.BOOKINGS,
        session_revision="session-1",
        result=InventoryDiscoveryResult((), InventoryCompleteness.INCOMPLETE),
        observed_at=NOW,
    )
    return owner.user_id


def _metrics(user_id: int, *, run_id: str = "inventory-run-1") -> InventoryExecutionMetrics:
    return InventoryExecutionMetrics(
        run_id=run_id,
        user_id=user_id,
        source="stagehand",
        terminal_status="partial",
        accepted_count=2,
        rejected_count=1,
        scope_count=1,
        page_count=2,
        detail_count=3,
        semantic_action_count=4,
        computer_action_count=1,
        input_tokens=1200,
        output_tokens=180,
        model_cost_micro_usd=42_000,
        latency_ms=12_500,
        fallback_used=True,
        safety_codes=("guard.popup_rejected",),
    )


def _reservation(*, property_name: str = "Hotel Example") -> ReservationObservation:
    return ReservationObservation(
        remote_id="agentic-remote-1",
        lifecycle=ReservationLifecycle.UPCOMING,
        observed_at=NOW,
        confirmation_id="6992391225",
        property_name=property_name,
        property_ref="hotel-example-ref",
        check_in=date(2026, 10, 1),
        check_out=date(2026, 10, 4),
        room_type="Deluxe King Room",
        booked_total=Money(Decimal("300"), "EUR"),
        refundable=True,
        refund_note="Free cancellation",
        refund_deadline=date(2026, 9, 30),
        occupancy=Occupancy(2, 1, 1),
        extraction_method="dom",
    )


def test_agentic_inventory_metrics_are_content_free_scoped_and_idempotent(
    tmp_path: Path,
) -> None:
    with SqliteStore(tmp_path / "booksaver.db") as store:
        user_id = _create_sync_run(store)
        repo = SqliteInventoryExecutionMetricsRepository(store)
        metrics = _metrics(user_id)

        repo.record(metrics)
        repo.record(metrics)

        assert repo.get_for_run(user_id=user_id, run_id=metrics.run_id) == metrics
        assert repo.get_for_run(user_id=user_id + 1, run_id=metrics.run_id) is None
        with pytest.raises(LookupError, match="Caller-scoped"):
            repo.record(replace(metrics, run_id="missing-run"))
        with pytest.raises(ValueError, match="already recorded"):
            repo.record(replace(metrics, terminal_status="failed"))

        columns = {
            row[1]
            for row in store.conn.execute("PRAGMA table_info(agentic_inventory_executions)")
        }
        assert columns == {
            "run_id",
            "user_id",
            "source",
            "terminal_status",
            "accepted_count",
            "rejected_count",
            "scope_count",
            "page_count",
            "detail_count",
            "semantic_action_count",
            "computer_action_count",
            "input_tokens",
            "output_tokens",
            "model_cost_micro_usd",
            "latency_ms",
            "fallback_used",
            "safety_codes_json",
        }


def test_inventory_metrics_reject_content_bearing_free_text() -> None:
    with pytest.raises(ValueError, match="source"):
        replace(_metrics(1), source="visible page text")
    with pytest.raises(ValueError, match="safety_codes"):
        replace(_metrics(1), safety_codes=("Booking.com showed a reservation",))


def test_schema_v17_migration_preserves_existing_sync_runs(tmp_path: Path) -> None:
    db_path = tmp_path / "v16.db"
    with SqliteStore(db_path) as store:
        user_id = _create_sync_run(store, run_id="preserved-v16-run")
        store.conn.execute("DROP TABLE agentic_inventory_executions")
        store.conn.execute("UPDATE schema_meta SET version = 16")
        store.conn.commit()

    with SqliteStore(db_path) as store:
        version = store.conn.execute("SELECT MAX(version) FROM schema_meta").fetchone()[0]
        preserved = store.conn.execute(
            "SELECT user_id FROM booking_sync_runs WHERE run_id = 'preserved-v16-run'"
        ).fetchone()

        assert version == SCHEMA_VERSION == 18
        assert preserved is not None
        assert preserved[0] == user_id
        assert (
            store.conn.execute(
                "SELECT 1 FROM sqlite_master "
                "WHERE type = 'table' AND name = 'agentic_inventory_executions'"
            ).fetchone()
            is not None
        )


def test_partial_agentic_positive_preserves_last_safe_projection_and_facts(
    tmp_path: Path,
) -> None:
    with SqliteStore(tmp_path / "booksaver.db") as store:
        owner = SqliteUserRepository(store).get_owner()
        repo = SqliteAccountReservationRepository(store)
        original = _reservation()
        repo.reconcile(
            user_id=owner.user_id,
            run_id="seed-safe-inventory",
            trigger=SynchronizationTrigger.BOOKINGS,
            session_revision="session-1",
            result=InventoryDiscoveryResult(
                (original,),
                InventoryCompleteness.INCOMPLETE,
            ),
            observed_at=NOW,
        )
        before = repo.list_for_user(owner.user_id)[0]
        partial = replace(
            original,
            observed_at=NOW + timedelta(minutes=1),
            property_name=None,
            property_ref=None,
            check_in=None,
            check_out=None,
            room_type=None,
            booked_total=None,
            refundable=None,
            refund_note="",
            refund_deadline=None,
            occupancy=None,
            extraction_method="agentic_inventory",
        )

        report = repo.reconcile(
            user_id=owner.user_id,
            run_id="agentic-partial-positive",
            trigger=SynchronizationTrigger.BOOKINGS,
            session_revision="session-1",
            result=InventoryDiscoveryResult(
                (partial,),
                InventoryCompleteness.INCOMPLETE,
            ),
            observed_at=NOW + timedelta(minutes=1),
        )
        after = repo.list_for_user(owner.user_id)[0]

        assert report.completeness is InventoryCompleteness.INCOMPLETE
        assert after.monitoring_booking_id == before.monitoring_booking_id
        assert after.observation.property_name == original.property_name
        assert after.observation.check_in == original.check_in
        assert after.observation.booked_total == original.booked_total
        assert after.observation.refundable is True
        assert repo.positively_observed_booking_ids_for_run(
            user_id=owner.user_id,
            run_id=report.run_id,
        ) == (before.monitoring_booking_id,)


def test_agentic_confirmation_match_merges_legacy_internal_remote_identity(
    tmp_path: Path,
) -> None:
    with SqliteStore(tmp_path / "booksaver.db") as store:
        owner = SqliteUserRepository(store).get_owner()
        repo = SqliteAccountReservationRepository(store)
        original = _reservation()
        repo.reconcile(
            user_id=owner.user_id,
            run_id="seed-internal-remote-id",
            trigger=SynchronizationTrigger.BOOKINGS,
            session_revision="session-1",
            result=InventoryDiscoveryResult((original,), InventoryCompleteness.INCOMPLETE),
            observed_at=NOW,
        )
        before = repo.list_for_user(owner.user_id)[0]
        agentic = replace(
            original,
            remote_id=original.confirmation_id or "",
            observed_at=NOW + timedelta(minutes=1),
            property_ref=None,
            room_type=None,
            booked_total=None,
            refundable=None,
            refund_note="",
            refund_deadline=None,
            occupancy=None,
            extraction_method="agentic_inventory",
        )

        report = repo.reconcile(
            user_id=owner.user_id,
            run_id="agentic-confirmation-match",
            trigger=SynchronizationTrigger.BOOKINGS,
            session_revision="session-1",
            result=InventoryDiscoveryResult((agentic,), InventoryCompleteness.INCOMPLETE),
            observed_at=NOW + timedelta(minutes=1),
        )
        rows = repo.list_for_user(owner.user_id)

        assert report.eligible == 1
        assert len(rows) == 1
        assert rows[0].account_reservation_id == before.account_reservation_id
        assert rows[0].observation.property_ref == original.property_ref
        assert repo.positively_observed_booking_ids_for_run(
            user_id=owner.user_id,
            run_id=report.run_id,
        ) == (before.monitoring_booking_id,)


def test_conflicting_agentic_positive_fails_closed_without_overwriting_safe_state(
    tmp_path: Path,
) -> None:
    with SqliteStore(tmp_path / "booksaver.db") as store:
        owner = SqliteUserRepository(store).get_owner()
        repo = SqliteAccountReservationRepository(store)
        original = _reservation()
        repo.reconcile(
            user_id=owner.user_id,
            run_id="seed-conflict-inventory",
            trigger=SynchronizationTrigger.BOOKINGS,
            session_revision="session-1",
            result=InventoryDiscoveryResult(
                (original,),
                InventoryCompleteness.INCOMPLETE,
            ),
            observed_at=NOW,
        )
        before = repo.list_for_user(owner.user_id)[0]
        conflicting = replace(
            original,
            observed_at=NOW + timedelta(minutes=1),
            property_name="Different Hotel",
            extraction_method="agentic_inventory",
        )

        report = repo.reconcile(
            user_id=owner.user_id,
            run_id="agentic-conflicting-positive",
            trigger=SynchronizationTrigger.BOOKINGS,
            session_revision="session-1",
            result=InventoryDiscoveryResult(
                (conflicting,),
                InventoryCompleteness.INCOMPLETE,
            ),
            observed_at=NOW + timedelta(minutes=1),
        )
        after = repo.list_for_user(owner.user_id)[0]

        assert report.completeness is InventoryCompleteness.FAILED
        assert report.failure_code is SynchronizationFailureCode.PERSISTENCE_CONFLICT
        assert after.monitoring_booking_id == before.monitoring_booking_id
        assert after.observation.property_name == original.property_name
        assert repo.positively_observed_booking_ids_for_run(
            user_id=owner.user_id,
            run_id=report.run_id,
        ) == ()


def test_agentic_lifecycle_conflict_cannot_requalify_a_saved_projection(
    tmp_path: Path,
) -> None:
    with SqliteStore(tmp_path / "booksaver.db") as store:
        owner = SqliteUserRepository(store).get_owner()
        repo = SqliteAccountReservationRepository(store)
        original = _reservation()
        repo.reconcile(
            user_id=owner.user_id,
            run_id="seed-lifecycle-conflict",
            trigger=SynchronizationTrigger.BOOKINGS,
            session_revision="session-1",
            result=InventoryDiscoveryResult(
                (original,),
                InventoryCompleteness.INCOMPLETE,
            ),
            observed_at=NOW,
        )
        conflicting = replace(
            original,
            lifecycle=ReservationLifecycle.CANCELLED,
            observed_at=NOW + timedelta(minutes=1),
            extraction_method="agentic_inventory",
        )

        report = repo.reconcile(
            user_id=owner.user_id,
            run_id="agentic-lifecycle-conflict",
            trigger=SynchronizationTrigger.BOOKINGS,
            session_revision="session-1",
            result=InventoryDiscoveryResult(
                (conflicting,),
                InventoryCompleteness.INCOMPLETE,
            ),
            observed_at=NOW + timedelta(minutes=1),
        )

        assert report.completeness is InventoryCompleteness.FAILED
        assert report.failure_code is SynchronizationFailureCode.PERSISTENCE_CONFLICT
        assert repo.positively_observed_booking_ids_for_run(
            user_id=owner.user_id,
            run_id=report.run_id,
        ) == ()
        assert repo.list_for_user(owner.user_id)[0].observation.lifecycle is (
            ReservationLifecycle.UPCOMING
        )


def test_complete_agentic_positive_fills_only_missing_safe_facts_and_projects(
    tmp_path: Path,
) -> None:
    with SqliteStore(tmp_path / "booksaver.db") as store:
        owner = SqliteUserRepository(store).get_owner()
        repo = SqliteAccountReservationRepository(store)
        complete = _reservation()
        incomplete = replace(
            complete,
            lifecycle=ReservationLifecycle.UNKNOWN,
            property_ref=None,
            check_in=None,
            check_out=None,
            room_type=None,
            booked_total=None,
            refundable=None,
            refund_note="",
            refund_deadline=None,
            occupancy=None,
        )
        seed = repo.reconcile(
            user_id=owner.user_id,
            run_id="seed-incomplete-agentic-target",
            trigger=SynchronizationTrigger.BOOKINGS,
            session_revision="session-1",
            result=InventoryDiscoveryResult(
                (incomplete,),
                InventoryCompleteness.INCOMPLETE,
            ),
            observed_at=NOW,
        )
        assert seed.eligible == 0
        assert repo.list_for_user(owner.user_id)[0].monitoring_booking_id is None

        report = repo.reconcile(
            user_id=owner.user_id,
            run_id="agentic-completes-safe-facts",
            trigger=SynchronizationTrigger.BOOKINGS,
            session_revision="session-1",
            result=InventoryDiscoveryResult(
                (
                    replace(
                        complete,
                        observed_at=NOW + timedelta(minutes=1),
                        extraction_method="agentic_inventory",
                    ),
                ),
                InventoryCompleteness.INCOMPLETE,
            ),
            observed_at=NOW + timedelta(minutes=1),
        )
        persisted = repo.list_for_user(owner.user_id)[0]

        assert report.eligible == 1
        assert persisted.monitoring_booking_id is not None
        assert persisted.observation.property_name == complete.property_name
        assert persisted.observation.check_in == complete.check_in
        assert persisted.observation.booked_total == complete.booked_total
        assert persisted.observation.occupancy == complete.occupancy
        assert repo.positively_observed_booking_ids_for_run(
            user_id=owner.user_id,
            run_id=report.run_id,
        ) == (persisted.monitoring_booking_id,)
