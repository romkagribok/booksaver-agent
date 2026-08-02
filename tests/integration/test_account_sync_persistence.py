import json
import sqlite3
from dataclasses import replace
from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from booksaver.application.account_sync import SynchronizeBookingAccount
from booksaver.application.ports import PageContent
from booksaver.domain.account_sync import (
    EligibilityReason,
    InventoryCompleteness,
    InventoryDiscoveryResult,
    InventoryRecoveryAudit,
    InventoryRecoveryOutcome,
    ReservationLifecycle,
    ReservationObservation,
    SynchronizationFailureCode,
    SynchronizationTrigger,
)
from booksaver.domain.user import UserAccessState
from booksaver.domain.value_objects import Money, Occupancy
from booksaver.infrastructure.browser.booking_account_inventory import (
    BookingComAccountInventorySource,
)
from booksaver.infrastructure.persistence.sqlite_store import (
    SCHEMA_VERSION,
    SqliteAccountReservationRepository,
    SqliteBookingRepository,
    SqliteStore,
    SqliteUserRepository,
)

NOW = datetime(2026, 7, 27, tzinfo=UTC)


def _recovery_audit() -> InventoryRecoveryAudit:
    return InventoryRecoveryAudit.from_operational_events(
        outcome=InventoryRecoveryOutcome.RECOVERED,
        step="inventory_scope",
        providers=("anthropic",),
        models=("claude-haiku-4-5", "claude-sonnet-4-5"),
        roles=("agent_brain", "inventory_interpreter"),
        prompt_versions=(
            "booking-browser-recovery-v2",
            "booking-inventory-interpretation-v1",
        ),
        llm_calls_used=2,
        input_tokens=340,
        output_tokens=55,
        action_count=1,
        duration_ms=125,
        operational_events=(
            {
                "kind": "agent_action",
                "step": "inventory_scope",
                "action": "click",
                "target_present": True,
                "tier": 1,
            },
            {
                "kind": "agent_outcome",
                "step": "inventory_scope",
                "outcome": "executed",
                "progress": True,
                "verified": True,
            },
        ),
    )


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


def test_contradictory_llm_candidate_cannot_overwrite_existing_eligible_reservation(
    tmp_path: Path,
) -> None:
    class Browser:
        def open_page(self, url: str) -> PageContent:
            return PageContent(url, "<main>Changed layout</main>", "Cancelled")

        def is_authenticated(self) -> bool:
            return True

    class Interpreter:
        def interpret(
            self, _page_text: str, source_url: str
        ) -> tuple[ReservationObservation, ...]:
            return (
                replace(
                    _eligible(),
                    lifecycle=ReservationLifecycle.CANCELLED,
                    refundable=False,
                    source_url=source_url,
                    extraction_method="llm_inventory",
                ),
            )

    with SqliteStore(tmp_path / "booksaver.db") as store:
        user = SqliteUserRepository(store).get_owner()
        repo = SqliteAccountReservationRepository(store)
        _reconcile(
            repo,
            user.user_id,
            "run-1",
            InventoryDiscoveryResult((_eligible(),), InventoryCompleteness.COMPLETE),
        )

        report = SynchronizeBookingAccount(
            BookingComAccountInventorySource(
                interpreter=Interpreter(),
                consume_interpreter_call=lambda: None,
                llm_calls_used=lambda: 1,
            ),
            repo,
            clock=lambda: NOW,
        ).execute(
            browser=Browser(),
            user_id=user.user_id,
            trigger=SynchronizationTrigger.BOOKINGS,
            session_revision="session-2",
        )

        reservation = repo.list_for_user(user.user_id)[0]
        projected = SqliteBookingRepository(store).list_active_for_user(user.user_id)

    assert report.completeness is InventoryCompleteness.FAILED
    assert reservation.observation.lifecycle is ReservationLifecycle.UPCOMING
    assert reservation.observation.refundable is True
    assert reservation.eligibility.is_eligible
    assert len(projected) == 1


def test_incomplete_llm_positive_preserves_existing_authoritative_projection(
    tmp_path: Path,
) -> None:
    assisted = replace(
        _eligible(),
        lifecycle=ReservationLifecycle.UNKNOWN,
        check_in=None,
        check_out=None,
        room_type=None,
        booked_total=None,
        refundable=None,
        occupancy=None,
        extraction_method="llm_inventory",
        source_url="https://secure.booking.com/myreservations.html",
    )

    with SqliteStore(tmp_path / "booksaver.db") as store:
        user = SqliteUserRepository(store).get_owner()
        repo = SqliteAccountReservationRepository(store)
        _reconcile(
            repo,
            user.user_id,
            "run-1",
            InventoryDiscoveryResult((_eligible(),), InventoryCompleteness.COMPLETE),
        )
        original_booking = SqliteBookingRepository(store).list_active_for_user(
            user.user_id
        )[0]

        _reconcile(
            repo,
            user.user_id,
            "run-2",
            InventoryDiscoveryResult((assisted,), InventoryCompleteness.INCOMPLETE),
        )

        reservation = repo.list_for_user(user.user_id)[0]
        active = SqliteBookingRepository(store).list_active_for_user(user.user_id)

    assert reservation.observation.lifecycle is ReservationLifecycle.UPCOMING
    assert reservation.observation.check_in == date(2027, 1, 10)
    assert reservation.observation.booked_total == Money.of("200", "USD")
    assert reservation.observation.refundable is True
    assert reservation.eligibility.is_eligible
    assert [item.booking_id for item in active] == [original_booking.booking_id]


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
        repo.attach_recovery_audit(
            user_id=user.user_id,
            run_id="run-purge",
            audit=_recovery_audit(),
        )

        users.purge(user.user_id)

        assert users.get_by_id(user.user_id) is None
        assert repo.list_for_user(user.user_id) == []
        assert repo.latest_run_for_user(user.user_id) is None
        assert (
            repo.recovery_audit_for_run(
                user_id=user.user_id, run_id="run-purge"
            )
            is None
        )
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


def test_recovery_audit_round_trip_is_redacted_and_latest_run_reconstructs_it(
    tmp_path: Path,
) -> None:
    with SqliteStore(tmp_path / "booksaver.db") as store:
        user = SqliteUserRepository(store).get_owner()
        repo = SqliteAccountReservationRepository(store)
        _reconcile(
            repo,
            user.user_id,
            "run-audit",
            InventoryDiscoveryResult((_eligible(),), InventoryCompleteness.COMPLETE),
        )
        audit = _recovery_audit()

        repo.attach_recovery_audit(
            user_id=user.user_id,
            run_id="run-audit",
            audit=audit,
        )
        repo.attach_recovery_audit(
            user_id=user.user_id,
            run_id="run-audit",
            audit=audit,
        )
        with pytest.raises(ValueError, match="already attached"):
            repo.attach_recovery_audit(
                user_id=user.user_id,
                run_id="run-audit",
                audit=replace(audit, duration_ms=126),
            )

        assert repo.recovery_audit_for_run(
            user_id=user.user_id, run_id="run-audit"
        ) == audit
        latest = repo.latest_run_for_user(user.user_id)
        assert latest is not None
        assert latest.recovery_audit == audit
        assert latest.recovery_outcome is InventoryRecoveryOutcome.RECOVERED
        assert latest.recovery_step == "inventory_scope"
        assert latest.llm_calls_used == 2

        row = store.conn.execute(
            "SELECT recovery_trace_json FROM booking_sync_runs WHERE run_id = ?",
            ("run-audit",),
        ).fetchone()
        trace = json.loads(row["recovery_trace_json"])
        assert set(trace[0]) == {
            "kind",
            "step",
            "action",
            "target_present",
            "tier",
        }
        assert all(
            forbidden not in row["recovery_trace_json"].lower()
            for forbidden in (
                "page_text",
                "confirmation",
                "remote_id",
                "cookie",
                "api_key",
                "reasoning",
            )
        )


def test_recovery_audit_access_is_scoped_by_user_and_run(tmp_path: Path) -> None:
    with SqliteStore(tmp_path / "booksaver.db") as store:
        users = SqliteUserRepository(store)
        owner = users.get_owner()
        other = users.get_or_create_by_telegram_id(333)
        repo = SqliteAccountReservationRepository(store)
        _reconcile(
            repo,
            owner.user_id,
            "run-owner-audit",
            InventoryDiscoveryResult((), InventoryCompleteness.COMPLETE),
        )

        with pytest.raises(LookupError, match="Caller-scoped"):
            repo.attach_recovery_audit(
                user_id=other.user_id,
                run_id="run-owner-audit",
                audit=_recovery_audit(),
            )
        assert (
            repo.recovery_audit_for_run(
                user_id=other.user_id, run_id="run-owner-audit"
            )
            is None
        )

        repo.attach_recovery_audit(
            user_id=owner.user_id,
            run_id="run-owner-audit",
            audit=_recovery_audit(),
        )
        assert (
            repo.recovery_audit_for_run(
                user_id=other.user_id, run_id="run-owner-audit"
            )
            is None
        )


def test_schema_v13_migration_preserves_v12_sync_runs(tmp_path: Path) -> None:
    db_path = tmp_path / "v12.db"
    conn = sqlite3.connect(db_path)
    conn.executescript(
        """
        CREATE TABLE schema_meta (version INTEGER NOT NULL, applied_at TEXT NOT NULL);
        INSERT INTO schema_meta VALUES (12, '2026-08-02T00:00:00+00:00');
        CREATE TABLE users (
            user_id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_user_id INTEGER UNIQUE,
            telegram_username TEXT,
            role TEXT NOT NULL CHECK(role IN ('owner', 'user')),
            access_state TEXT NOT NULL CHECK(access_state IN ('active', 'revoked')),
            encrypted_key BLOB,
            created_at TEXT NOT NULL
        );
        CREATE UNIQUE INDEX idx_users_single_owner
            ON users(role) WHERE role = 'owner';
        INSERT INTO users VALUES (
            1, 111, 'owner', 'owner', 'active', NULL,
            '2026-08-02T00:00:00+00:00'
        );
        CREATE TABLE booking_sync_runs (
            run_id TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(user_id),
            trigger TEXT NOT NULL,
            started_at TEXT NOT NULL,
            completed_at TEXT NOT NULL,
            completeness TEXT NOT NULL,
            failure_code TEXT,
            failure_detail TEXT,
            discovered_count INTEGER NOT NULL,
            eligible_count INTEGER NOT NULL,
            ineligible_count INTEGER NOT NULL,
            session_revision TEXT NOT NULL
        );
        INSERT INTO booking_sync_runs VALUES (
            'preserved-v12-run', 1, 'bookings',
            '2026-08-02T00:00:00+00:00', '2026-08-02T00:00:01+00:00',
            'complete', NULL, NULL, 2, 1, 1, 'session-v12'
        );
        """
    )
    conn.commit()
    conn.close()

    with SqliteStore(db_path) as store:
        columns = {
            row[1] for row in store.conn.execute("PRAGMA table_info(booking_sync_runs)")
        }
        version = store.conn.execute(
            "SELECT MAX(version) FROM schema_meta"
        ).fetchone()[0]
        repo = SqliteAccountReservationRepository(store)
        legacy = repo.latest_run_for_user(1)

        assert version == SCHEMA_VERSION == 13
        assert {
            "recovery_outcome",
            "recovery_step",
            "recovery_providers_json",
            "recovery_models_json",
            "recovery_roles_json",
            "recovery_prompt_versions_json",
            "recovery_llm_calls",
            "recovery_input_tokens",
            "recovery_output_tokens",
            "recovery_action_count",
            "recovery_duration_ms",
            "recovery_trace_json",
        } <= columns
        assert legacy is not None
        assert legacy.discovered == 2
        assert legacy.recovery_audit is None

        repo.attach_recovery_audit(
            user_id=1,
            run_id="preserved-v12-run",
            audit=_recovery_audit(),
        )
        assert repo.recovery_audit_for_run(
            user_id=1, run_id="preserved-v12-run"
        ) == _recovery_audit()
