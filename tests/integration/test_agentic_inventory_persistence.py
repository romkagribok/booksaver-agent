from __future__ import annotations

from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest
from _pytest.logging import LogCaptureFixture

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
    tmp_path: Path, caplog: LogCaptureFixture,
) -> None:
    with SqliteStore(tmp_path / "booksaver.db") as store:
        owner = SqliteUserRepository(store).get_owner()
        repo = SqliteAccountReservationRepository(store)
        original = replace(
            _reservation(), property_ref="https://www.booking.com/hotel/us/hotel-example.html",
        )
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
            property_ref="https://www.booking.com/hotel/us/different-hotel.en-us.html",
            room_type="Different Room",
            extraction_method="agentic_inventory",
        )

        with caplog.at_level("WARNING"):
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
        assert after.observation.property_ref == original.property_ref
        assert after.observation.room_type == original.room_type
        assert repo.positively_observed_booking_ids_for_run(
            user_id=owner.user_id,
            run_id=report.run_id,
        ) == ()
        # The conflict names the disagreeing fields for operators without leaking content.
        assert "agentic-conflicting-positive" in caplog.text
        assert "property_ref" in caplog.text
        assert "room_type" in caplog.text
        assert "different-hotel" not in caplog.text
        assert "6992391225" not in caplog.text


@pytest.mark.parametrize(
    "stored_ref, observed_ref",
    [
        (
            "https://www.booking.com/hotel/us/hotel-example.html",
            "https://www.booking.com/hotel/us/hotel-example.en-us.html",
        ),
        (
            "https://www.booking.com/hotel/us/hotel-example.en-gb.html",
            "https://www.booking.com/hotel/us/hotel-example.html",
        ),
        (
            "https://secure.booking.com/hotel/us/hotel-example.html",
            "https://www.booking.com/hotel/us/hotel-example.en-us.html",
        ),
    ],
)
def test_agentic_refresh_accepts_renamed_property_and_locale_variant_reference(
    tmp_path: Path, stored_ref: str, observed_ref: str,
) -> None:
    """An anchored refresh keeps booked facts and the stored URL but follows a renamed hotel."""
    with SqliteStore(tmp_path / "booksaver.db") as store:
        owner = SqliteUserRepository(store).get_owner()
        repo = SqliteAccountReservationRepository(store)
        original = replace(_reservation(), property_ref=stored_ref)
        repo.reconcile(
            user_id=owner.user_id,
            run_id="seed-legacy-reference",
            trigger=SynchronizationTrigger.BOOKINGS,
            session_revision="session-1",
            result=InventoryDiscoveryResult((original,), InventoryCompleteness.INCOMPLETE),
            observed_at=NOW,
        )
        before = repo.list_for_user(owner.user_id)[0]
        refreshed = replace(
            original,
            remote_id=original.confirmation_id or "",
            observed_at=NOW + timedelta(minutes=1),
            property_name="Hotel Example by Marriott",
            property_ref=observed_ref,
            booked_total=None,
            refund_deadline=None,
            extraction_method="agentic_inventory",
            property_anchor_verified=True,
        )

        report = repo.reconcile(
            user_id=owner.user_id,
            run_id="agentic-locale-variant",
            trigger=SynchronizationTrigger.BOOKINGS,
            session_revision="session-1",
            result=InventoryDiscoveryResult((refreshed,), InventoryCompleteness.INCOMPLETE),
            observed_at=NOW + timedelta(minutes=1),
        )
        after = repo.list_for_user(owner.user_id)[0]
        projection = store.conn.execute(
            "SELECT property_name, property_ref FROM bookings WHERE booking_id = ?",
            (after.monitoring_booking_id,),
        ).fetchone()

        assert report.completeness is InventoryCompleteness.INCOMPLETE
        assert report.failure_code is None
        assert report.eligible == 1
        assert after.account_reservation_id == before.account_reservation_id
        assert after.monitoring_booking_id == before.monitoring_booking_id
        assert after.observation.property_name == "Hotel Example by Marriott"
        assert after.observation.property_ref == stored_ref
        assert after.observation.booked_total == original.booked_total
        assert after.observation.refund_deadline == original.refund_deadline
        assert after.last_sync_run_id == report.run_id
        assert tuple(projection) == ("Hotel Example by Marriott", stored_ref)


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


def test_empty_upcoming_observation_survives_reload_without_removing_saved_booking(tmp_path):
    with SqliteStore(tmp_path / "booksaver.db") as store:
        owner = SqliteUserRepository(store).get_owner()
        repo = SqliteAccountReservationRepository(store)
        repo.reconcile(
            user_id=owner.user_id, run_id="saved-before-empty",
            trigger=SynchronizationTrigger.BOOKINGS, session_revision="session-1",
            result=InventoryDiscoveryResult((_reservation(),), InventoryCompleteness.INCOMPLETE),
            observed_at=NOW,
        )
        before = repo.list_for_user(owner.user_id)
        repo.reconcile(
            user_id=owner.user_id, run_id="empty-upcoming",
            trigger=SynchronizationTrigger.BOOKINGS, session_revision="session-1",
            result=InventoryDiscoveryResult((), InventoryCompleteness.INCOMPLETE),
            observed_at=NOW + timedelta(minutes=1),
        )
        SqliteInventoryExecutionMetricsRepository(store).record(replace(
            _metrics(owner.user_id, run_id="empty-upcoming"), terminal_status="empty_upcoming",
            accepted_count=0, rejected_count=0, scope_count=0, page_count=0, detail_count=0,
        ))
        after = repo.list_for_user(owner.user_id)
        report = repo.latest_run_for_user(owner.user_id)
        assert report is not None and report.upcoming_empty_observed
        assert not report.succeeded
        assert after == before
        assert after[0].monitoring_booking_id is not None


def test_empty_raw_terminal_cannot_mask_failed_validation_on_reload(tmp_path):
    with SqliteStore(tmp_path / "booksaver.db") as store:
        owner = SqliteUserRepository(store).get_owner()
        repo = SqliteAccountReservationRepository(store)
        repo.reconcile(
            user_id=owner.user_id, run_id="expired-empty",
            trigger=SynchronizationTrigger.BOOKINGS, session_revision="session-1",
            result=InventoryDiscoveryResult.failed(
                SynchronizationFailureCode.NAVIGATION_FAILED, "Execution limit exceeded"
            ), observed_at=NOW,
        )
        SqliteInventoryExecutionMetricsRepository(store).record(replace(
            _metrics(owner.user_id, run_id="expired-empty"), terminal_status="empty_upcoming",
            accepted_count=0, rejected_count=0, scope_count=0, page_count=0, detail_count=0,
        ))
        report = repo.latest_run_for_user(owner.user_id)
        assert report is not None and not report.upcoming_empty_observed
        assert report.failure_code is SynchronizationFailureCode.NAVIGATION_FAILED


_STORED_URL = "https://www.booking.com/hotel/us/hotel-example.html"


@pytest.mark.parametrize("anchored", [False, True])
@pytest.mark.parametrize(
    "stored_ref, observed_name, observed_ref",
    [
        # A reference that is not a recognized English Booking hotel URL proves nothing.
        (_STORED_URL, "Other Hotel", "https://www.booking.com/hotel/fr/other-hotel.fr.html"),
        (_STORED_URL, "Other Hotel", "https://www.booking.com/hotel/us/other-hotel.html/"),
        (_STORED_URL, "Other Hotel", "Other Hotel"),
        # A rename without any URL cannot be tied to the saved hotel.
        (_STORED_URL, "Other Hotel", None),
        # A legacy non-URL reference is never replaced by an unproven model-reported URL.
        (
            "legacy-hotel-id-12345",
            "Hotel Example",
            "https://www.booking.com/hotel/us/hotel-example.en-us.html",
        ),
    ],
)
def test_agentic_refresh_rejects_unproven_property_change(
    tmp_path: Path, stored_ref: str, observed_name: str, observed_ref: str | None, anchored: bool,
) -> None:
    """Name and URL feed price checks, so only a URL-proven same hotel may change them."""
    with SqliteStore(tmp_path / "booksaver.db") as store:
        owner = SqliteUserRepository(store).get_owner()
        repo = SqliteAccountReservationRepository(store)
        original = replace(_reservation(), property_ref=stored_ref)
        repo.reconcile(
            user_id=owner.user_id,
            run_id="seed-unproven-change",
            trigger=SynchronizationTrigger.BOOKINGS,
            session_revision="session-1",
            result=InventoryDiscoveryResult((original,), InventoryCompleteness.INCOMPLETE),
            observed_at=NOW,
        )
        before = repo.list_for_user(owner.user_id)
        changed = replace(
            original,
            remote_id=original.confirmation_id or "",
            observed_at=NOW + timedelta(minutes=1),
            property_name=observed_name,
            property_ref=observed_ref,
            extraction_method="agentic_inventory",
            property_anchor_verified=anchored,
        )

        report = repo.reconcile(
            user_id=owner.user_id,
            run_id="agentic-unproven-change",
            trigger=SynchronizationTrigger.BOOKINGS,
            session_revision="session-1",
            result=InventoryDiscoveryResult((changed,), InventoryCompleteness.INCOMPLETE),
            observed_at=NOW + timedelta(minutes=1),
        )

        assert report.failure_code is SynchronizationFailureCode.PERSISTENCE_CONFLICT
        assert repo.list_for_user(owner.user_id) == before


def test_provider_submitted_rename_is_rejected_even_with_matching_url(tmp_path: Path) -> None:
    """Only a code-owned anchor ties a new name to the URL; provider output cannot rename."""
    with SqliteStore(tmp_path / "booksaver.db") as store:
        owner = SqliteUserRepository(store).get_owner()
        repo = SqliteAccountReservationRepository(store)
        original = replace(_reservation(), property_ref=_STORED_URL)
        repo.reconcile(
            user_id=owner.user_id,
            run_id="seed-provider-rename",
            trigger=SynchronizationTrigger.BOOKINGS,
            session_revision="session-1",
            result=InventoryDiscoveryResult((original,), InventoryCompleteness.INCOMPLETE),
            observed_at=NOW,
        )
        before = repo.list_for_user(owner.user_id)
        renamed = replace(
            original,
            remote_id=original.confirmation_id or "",
            observed_at=NOW + timedelta(minutes=1),
            property_name="Other Hotel",
            property_ref="https://www.booking.com/hotel/us/hotel-example.en-us.html",
            extraction_method="agentic_inventory",
        )

        report = repo.reconcile(
            user_id=owner.user_id,
            run_id="agentic-provider-rename",
            trigger=SynchronizationTrigger.BOOKINGS,
            session_revision="session-1",
            result=InventoryDiscoveryResult((renamed,), InventoryCompleteness.INCOMPLETE),
            observed_at=NOW + timedelta(minutes=1),
        )

        assert report.failure_code is SynchronizationFailureCode.PERSISTENCE_CONFLICT
        assert repo.list_for_user(owner.user_id) == before


def test_locale_variant_without_rename_needs_no_anchor(tmp_path: Path) -> None:
    """The motivating legacy-URL refresh succeeds from any agentic source when names agree."""
    with SqliteStore(tmp_path / "booksaver.db") as store:
        owner = SqliteUserRepository(store).get_owner()
        repo = SqliteAccountReservationRepository(store)
        original = replace(_reservation(), property_ref=_STORED_URL)
        repo.reconcile(
            user_id=owner.user_id,
            run_id="seed-locale-only",
            trigger=SynchronizationTrigger.BOOKINGS,
            session_revision="session-1",
            result=InventoryDiscoveryResult((original,), InventoryCompleteness.INCOMPLETE),
            observed_at=NOW,
        )
        refreshed = replace(
            original,
            remote_id=original.confirmation_id or "",
            observed_at=NOW + timedelta(minutes=1),
            property_ref="https://secure.booking.com/hotel/us/hotel-example.en-us.html",
            extraction_method="agentic_inventory",
        )

        report = repo.reconcile(
            user_id=owner.user_id,
            run_id="agentic-locale-only",
            trigger=SynchronizationTrigger.BOOKINGS,
            session_revision="session-1",
            result=InventoryDiscoveryResult((refreshed,), InventoryCompleteness.INCOMPLETE),
            observed_at=NOW + timedelta(minutes=1),
        )

        assert report.failure_code is None
        assert report.eligible == 1
        assert repo.list_for_user(owner.user_id)[0].observation.property_ref == _STORED_URL
