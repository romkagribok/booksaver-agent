from __future__ import annotations

import json
import threading
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from booksaver.application.browser_executor import InMemorySessionLeaseBroker
from booksaver.application.inventory_executor import (
    InventoryObservationValidator,
    _to_reservation_observation,
    _valid_positive,
)
from booksaver.daemon.check_coordinator import ImmediateAdmission, InventoryCompletion
from booksaver.daemon.scheduler import Scheduler
from booksaver.domain.account_sync import (
    EligibilityReason,
    InventoryCompleteness,
    InventoryDiscoveryResult,
    ReservationLifecycle,
    SynchronizationFailureCode,
    SynchronizationTrigger,
)
from booksaver.domain.browser_executor import (
    EvidenceCompleteness,
    ExecutionLimits,
    ObservationSource,
    RedactedProvenance,
)
from booksaver.domain.inventory_executor import (
    InventoryExecutionRequest,
    InventoryExecutionResult,
    InventoryExecutionStatus,
    inventory_session_subject,
)
from booksaver.infrastructure.browser.browser_use_inventory_executor import (
    BrowserUseReservationFactsSubmission,
    BrowserUseReservationPayload,
    BrowserUseReservationSubmission,
    _attach_reservation_facts,
    _inventory_submission_observation,
    _map_browser_use_observation,
    _record_reservation_identity,
)
from booksaver.infrastructure.persistence.sqlite_store import (
    SqliteAccountReservationRepository,
    SqliteStore,
    SqliteUserRepository,
)
from booksaver.infrastructure.telegram.commands_readonly import register_readonly_commands
from booksaver.infrastructure.telegram.router import CommandRouter, IncomingCommand
from tests.support.executors import FakeInventoryBrowserExecutor
from tests.unit.daemon.test_check_coordinator import (
    BrowserContext,
    _build_coordinator,
    _config,
    _seed_session,
    _session_repo,
)


@pytest.mark.parametrize(
    ("scope", "lifecycle", "expected_lifecycle", "accepted", "eligible", "missing_fact"),
    [
        ("upcoming", "upcoming", ReservationLifecycle.UPCOMING, True, True, None),
        ("upcoming", "current", ReservationLifecycle.CURRENT, True, False, None),
        ("upcoming", None, ReservationLifecycle.UNKNOWN, True, False, None),
        ("upcoming", "cancelled", None, False, False, None),
        ("cancelled", "current", None, False, False, None),
        ("cancelled", "cancelled", ReservationLifecycle.CANCELLED, True, False, None),
        ("upcoming", "upcoming", ReservationLifecycle.UPCOMING, True, False, "property_reference"),
        ("upcoming", "upcoming", ReservationLifecycle.UPCOMING, True, False, "refundability"),
    ],
)
def test_first_time_lifecycle_survives_validation_persistence_and_rendering(
    tmp_path: Path,
    scope: str,
    lifecycle: str | None,
    expected_lifecycle: ReservationLifecycle | None,
    accepted: bool,
    eligible: bool,
    missing_fact: str | None,
) -> None:
    now = datetime.now(UTC)
    check_in = now.date() + timedelta(days=30)
    check_out = check_in + timedelta(days=2)
    if lifecycle == "current":
        check_in = now.date() - timedelta(days=1)
        check_out = now.date() + timedelta(days=2)
    db_path = tmp_path / "booksaver.db"
    with SqliteStore(db_path) as store:
        users = SqliteUserRepository(store)
        caller = users.get_or_create_by_telegram_id(4242)
        assert not SqliteAccountReservationRepository(store).list_for_user(caller.user_id)
    broker = InMemorySessionLeaseBroker()
    lease = broker.issue(
        owner_user_id=caller.user_id,
        subject_id=inventory_session_subject(caller.user_id),
        execution_id="new-lifecycle-test",
        session_material=b"synthetic-unused-session",
    )
    request = InventoryExecutionRequest(
        execution_id="new-lifecycle-test",
        owner_user_id=caller.user_id,
        session_lease=lease,
        limits=ExecutionLimits(deadline=now + timedelta(minutes=3)),
    )
    reservations: list[BrowserUseReservationPayload] = []
    assert _record_reservation_identity(
        reservations,
        BrowserUseReservationSubmission(
            confirmation_id="NEW-LIFECYCLE-ONLY",
            scope=scope,
            identity_evidence="complete",
        ),
    )
    facts = {
        "property_name": "Synthetic Hotel",
        "property_reference": "synthetic-hotel-reference",
        "check_in": check_in.isoformat(),
        "check_out": check_out.isoformat(),
        "room_type": "Double",
        "booked_total": "200.00",
        "currency": "EUR",
        "all_in": "explicit",
        "refundability": "explicit_refundable",
        "refundability_text": "Free cancellation",
        "refund_deadline": (check_in - timedelta(days=1)).isoformat(),
        "adults": "2",
        "children": "0",
        "rooms": "1",
    }
    if missing_fact is not None:
        facts.pop(missing_fact)
    if missing_fact == "refundability":
        facts.pop("refundability_text")
        facts.pop("refund_deadline")
    assert _attach_reservation_facts(
        reservations,
        BrowserUseReservationFactsSubmission(
            confirmation_id="NEW-LIFECYCLE-ONLY",
            facts_json=json.dumps(facts),
        ),
    )
    if lifecycle is not None:
        # Isolate status acceptance from the previously submitted reservation facts.
        _attach_reservation_facts(
            reservations,
            BrowserUseReservationFactsSubmission(
                confirmation_id="NEW-LIFECYCLE-ONLY",
                facts_json=json.dumps({"lifecycle": lifecycle}),
            ),
        )
    payload = _inventory_submission_observation(reservations, requested_success=True)
    assert payload is not None
    scopes, observed = _map_browser_use_observation(payload)
    assert all(item.completeness is EvidenceCompleteness.INCOMPLETE for item in observed)
    validation = InventoryObservationValidator(clock=lambda: now).validate(
        request,
        InventoryExecutionResult(
            status=InventoryExecutionStatus.OBSERVED,
            authenticated=True,
            scopes=scopes,
            reservations=observed,
            provenance=RedactedProvenance(
                source=ObservationSource.BROWSER_USE_INVENTORY_SUBMISSION,
                action_count=2,
                evidence_item_count=1,
                schema_version="inventory-observation-v1",
            ),
        ),
    )
    with SqliteStore(db_path) as store:
        repository = SqliteAccountReservationRepository(store)
        report = repository.reconcile(
            user_id=caller.user_id,
            run_id="new-lifecycle-run",
            trigger=SynchronizationTrigger.BOOKINGS,
            session_revision="unused-synthetic-revision",
            result=validation.to_discovery_result(),
            observed_at=now,
        )
        persisted = tuple(repository.list_for_user(caller.user_id))
    assert report.completeness is InventoryCompleteness.INCOMPLETE
    assert bool(persisted) is accepted
    if accepted:
        assert persisted[0].observation.lifecycle is expected_lifecycle
        assert persisted[0].eligibility.is_eligible is eligible
        assert report.eligible == int(eligible)
        if lifecycle in {None, "current"}:
            assert EligibilityReason.NOT_UPCOMING in persisted[0].eligibility.reasons
        if lifecycle == "cancelled":
            assert EligibilityReason.CANCELLED in persisted[0].eligibility.reasons
        if missing_fact == "property_reference":
            assert EligibilityReason.MISSING_PROPERTY in persisted[0].eligibility.reasons
        if missing_fact == "refundability":
            assert EligibilityReason.REFUNDABILITY_UNKNOWN in persisted[0].eligibility.reasons
    else:
        assert report.failure_code is SynchronizationFailureCode.EXTRACTION_AMBIGUOUS
        assert report.eligible == 0

    class Coordinator:
        def request_inventory(self, user_id, callback):
            assert user_id == 4242
            callback(InventoryCompletion(report, persisted))
            return ImmediateAdmission.ACCEPTED

    messages: list[str] = []
    router = CommandRouter()
    register_readonly_commands(
        router=router,
        reply=lambda _chat_id, text: messages.append(text),
        db_path=db_path,
        scheduler=Scheduler(),
        check_coordinator=Coordinator(),  # type: ignore[arg-type]
    )
    router.dispatch(
        IncomingCommand(
            user_id=4242,
            chat_id=4242,
            command="/bookings",
            args="",
            raw_text="/bookings",
        )
    )
    text = "\n".join(messages)
    if eligible:
        assert "NEW-LIFECYCLE-ONLY" in text
        assert "Price checks available" in text
    else:
        assert "Price checks available" not in text
    broker.close(lease)


@pytest.mark.parametrize(
    ("scope", "lifecycle", "seed_lifecycle", "malformed_price"),
    [
        ("upcoming", "upcoming", ReservationLifecycle.UNKNOWN, False),
        ("upcoming", "upcoming", ReservationLifecycle.UPCOMING, False),
        ("upcoming", "cancelled", ReservationLifecycle.UPCOMING, True),
        ("upcoming", "completed", ReservationLifecycle.UPCOMING, True),
        ("cancelled", "current", ReservationLifecycle.UPCOMING, True),
    ],
)
def test_coordinator_fills_sparse_saved_facts_without_accepting_status_contradictions(
    tmp_path: Path,
    scope: str,
    lifecycle: str,
    seed_lifecycle: ReservationLifecycle,
    malformed_price: bool,
) -> None:
    now = datetime.now(UTC)
    check_in = now.date() + timedelta(days=30)
    full = BrowserUseReservationPayload(
        remote_id="SAVED-DETAIL-RETRY",
        confirmation_id="SAVED-DETAIL-RETRY",
        scope="upcoming",
        lifecycle="upcoming",
        identity_evidence="complete",
        property_name="Synthetic Hotel",
        property_reference="synthetic-hotel-reference",
        check_in=check_in.isoformat(),
        check_out=(check_in + timedelta(days=2)).isoformat(),
        room_type="Double",
        booked_total="200.00",
        currency="EUR",
        all_in="explicit",
        refundability="explicit_refundable",
        refundability_text="Free cancellation",
        refund_deadline=(check_in - timedelta(days=1)).isoformat(),
        adults="2",
        children="0",
        rooms="1",
    )
    full_payload = _inventory_submission_observation([full], requested_success=True)
    assert full_payload is not None
    _, full_observed = _map_browser_use_observation(full_payload)
    seed = _to_reservation_observation(full_observed[0], now)
    if not malformed_price:
        seed = replace(
            seed,
            lifecycle=seed_lifecycle,
            property_ref=None,
            booked_total=None,
            occupancy=None,
            refundable=None,
            refund_note="",
            refund_deadline=None,
        )
    db_path = tmp_path / "booksaver.db"
    with SqliteStore(db_path) as store:
        users = SqliteUserRepository(store)
        caller = users.get_owner()
        users.link_telegram_id(caller.user_id, 101)
        repository = SqliteAccountReservationRepository(store)
        repository.reconcile(
            user_id=caller.user_id,
            run_id="seed-detail-retry",
            trigger=SynchronizationTrigger.BOOKINGS,
            session_revision="seed-session",
            result=InventoryDiscoveryResult((seed,), InventoryCompleteness.INCOMPLETE),
            observed_at=now,
        )
        before = repository.list_for_user(caller.user_id)
        assert before[0].eligibility.is_eligible is malformed_price

    incoming = full.model_copy(
        update={
            "scope": scope,
            "lifecycle": lifecycle,
            "booked_total": "malformed-total" if malformed_price else full.booked_total,
        }
    )
    payload = _inventory_submission_observation([incoming], requested_success=True)
    assert payload is not None
    scopes, reservations = _map_browser_use_observation(payload)
    assert reservations[0].lifecycle is ReservationLifecycle(lifecycle)
    executor = FakeInventoryBrowserExecutor(
        [
            InventoryExecutionResult(
                status=InventoryExecutionStatus.OBSERVED,
                authenticated=True,
                scopes=scopes,
                reservations=reservations,
                provenance=RedactedProvenance(
                    source=ObservationSource.BROWSER_USE_INVENTORY_SUBMISSION,
                    action_count=2,
                    evidence_item_count=1,
                    schema_version="inventory-observation-v1",
                ),
            )
        ]
    )
    sessions = _session_repo(tmp_path)
    _seed_session(sessions, caller.user_id)
    coordinator = _build_coordinator(
        _config(tmp_path),
        browser_factory=BrowserContext,
        session_repository=sessions,
        agentic_inventory_executor_factory=lambda _budget, _leases: executor,
        bookings_inventory_executor_factory=lambda _budget, _leases: executor,
    )
    done = threading.Event()
    completions: list[InventoryCompletion] = []

    def completed(result: InventoryCompletion) -> None:
        completions.append(result)
        done.set()

    assert coordinator.request_inventory(101, completed) is ImmediateAdmission.ACCEPTED
    assert done.wait(2)
    assert len(completions) == 1
    assert len(executor.requests) == 1
    request = executor.requests[0]
    assert request.owner_user_id == caller.user_id
    assert request.known_confirmation_ids == (full.confirmation_id,)
    with SqliteStore(db_path) as store:
        after = SqliteAccountReservationRepository(store).list_for_user(caller.user_id)
        metrics = store.conn.execute(
            "SELECT accepted_count FROM agentic_inventory_executions WHERE user_id = ?",
            (caller.user_id,),
        ).fetchall()
    assert len(after) == 1
    assert after[0].account_reservation_id == before[0].account_reservation_id
    if malformed_price:
        assert after == before
        assert [row["accepted_count"] for row in metrics] == [0]
        assert completions[0].report.failure_code is SynchronizationFailureCode.EXTRACTION_AMBIGUOUS
    else:
        assert request.known_reservations == ()
        assert after[0].observation.lifecycle is ReservationLifecycle.UPCOMING
        assert after[0].eligibility.is_eligible
        assert after[0].observation.property_ref == "synthetic-hotel-reference"
        assert after[0].observation.booked_total == full_observed[0].booked_total
        assert after[0].observation.occupancy == full_observed[0].occupancy
        assert after[0].observation.refundable is True
        assert [row["accepted_count"] for row in metrics] == [1]
        assert completions[0].report.failure_code is None


@pytest.mark.parametrize("contradictory_lifecycle", ["cancelled", "current"])
@pytest.mark.parametrize("malformed_price", [False, True])
def test_later_contradictory_lifecycle_cannot_leave_an_accepted_upcoming_positive(
    contradictory_lifecycle: str,
    malformed_price: bool,
) -> None:
    rows: list[BrowserUseReservationPayload] = []
    assert _record_reservation_identity(
        rows,
        BrowserUseReservationSubmission(
            confirmation_id="LIFECYCLE-CONFLICT",
            scope="upcoming",
            identity_evidence="complete",
        ),
    )
    assert _attach_reservation_facts(
        rows,
        BrowserUseReservationFactsSubmission(
            confirmation_id="LIFECYCLE-CONFLICT",
            facts_json='{"lifecycle":"upcoming"}',
        ),
    )
    assert not _attach_reservation_facts(
        rows,
        BrowserUseReservationFactsSubmission(
            confirmation_id="LIFECYCLE-CONFLICT",
            facts_json=json.dumps({"lifecycle": contradictory_lifecycle}),
        ),
    )
    assert rows[0].completeness == "conflicting"
    assert _attach_reservation_facts(
        rows,
        BrowserUseReservationFactsSubmission(
            confirmation_id="LIFECYCLE-CONFLICT",
            facts_json=json.dumps(
                {
                    "property_name": "Synthetic Hotel",
                    "booked_total": "malformed-price" if malformed_price else "200.00",
                    "currency": "EUR",
                    "all_in": "explicit",
                }
            ),
        ),
    )
    # Later accepted facts must not clear a contradiction, including the malformed-fact fallback.
    payload = _inventory_submission_observation(rows, requested_success=True)
    assert payload is not None
    _, observations = _map_browser_use_observation(payload)
    assert observations[0].completeness is EvidenceCompleteness.CONFLICTING
    assert not _valid_positive(observations[0])


def test_case_normalized_repeat_lifecycle_is_not_a_conflict() -> None:
    rows = [
        BrowserUseReservationPayload(
            remote_id="SAME-LIFECYCLE",
            confirmation_id="SAME-LIFECYCLE",
            scope="upcoming",
            lifecycle="upcoming",
            identity_evidence="complete",
        )
    ]
    _attach_reservation_facts(
        rows,
        BrowserUseReservationFactsSubmission(
            confirmation_id="SAME-LIFECYCLE",
            facts_json='{"lifecycle":" UPCOMING "}',
        ),
    )
    assert rows[0].completeness != "conflicting"
    payload = _inventory_submission_observation(rows, requested_success=True)
    assert payload is not None
    _, observations = _map_browser_use_observation(payload)
    assert observations[0].lifecycle is ReservationLifecycle.UPCOMING
    assert _valid_positive(observations[0])
