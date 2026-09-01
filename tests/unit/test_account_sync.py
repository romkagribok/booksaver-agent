from datetime import UTC, date, datetime

from booksaver.application.account_sync import SynchronizeBookingAccount
from booksaver.domain.account_sync import (
    EligibilityReason,
    InventoryCompleteness,
    InventoryDiscoveryResult,
    ReservationLifecycle,
    ReservationObservation,
    SynchronizationFailureCode,
    SynchronizationReport,
    SynchronizationTrigger,
    evaluate_eligibility,
    remote_key_hash,
)
from booksaver.domain.browser_resilience import (
    DiagnosisProvenance,
    DomStepId,
    OperatorAction,
    TerminalBrowserDiagnosis,
    TerminalBrowserReason,
)
from booksaver.domain.value_objects import Money, Occupancy


def _observation(**overrides: object) -> ReservationObservation:
    values: dict[str, object] = {
        "remote_id": "reservation-1",
        "lifecycle": ReservationLifecycle.UPCOMING,
        "observed_at": datetime(2026, 7, 27, tzinfo=UTC),
        "confirmation_id": "CONF-1",
        "property_name": "Hotel Example",
        "property_ref": "hotel-example",
        "check_in": date(2027, 1, 10),
        "check_out": date(2027, 1, 12),
        "room_type": "King room",
        "booked_total": Money.of("200", "USD"),
        "refundable": True,
        "occupancy": Occupancy(2, 0, 1),
    }
    values.update(overrides)
    return ReservationObservation(**values)  # type: ignore[arg-type]


def test_complete_refundable_upcoming_observation_is_eligible() -> None:
    decision = evaluate_eligibility(_observation(), today=date(2026, 7, 27))

    assert decision.is_eligible
    assert decision.reasons == ()


def test_incomplete_observation_keeps_every_specific_reason() -> None:
    decision = evaluate_eligibility(
        _observation(
            confirmation_id=None,
            room_type=None,
            booked_total=None,
            refundable=None,
            occupancy=None,
        ),
        today=date(2026, 7, 27),
    )

    assert not decision.is_eligible
    assert set(decision.reasons) == {
        EligibilityReason.REFUNDABILITY_UNKNOWN,
        EligibilityReason.MISSING_CONFIRMATION,
        EligibilityReason.MISSING_ROOM_TYPE,
        EligibilityReason.MISSING_OCCUPANCY,
        EligibilityReason.MISSING_BOOKED_TOTAL,
    }


def test_remote_identity_hash_is_caller_scoped() -> None:
    assert remote_key_hash(1, "same") != remote_key_hash(2, "same")
    assert remote_key_hash(1, "same") == remote_key_hash(1, " same ")


def test_failed_discovery_requires_redacted_failure_code() -> None:
    result = InventoryDiscoveryResult.failed(
        SynchronizationFailureCode.AUTH_REQUIRED,
        "Booking.com account authentication is required.",
    )

    assert result.completeness is InventoryCompleteness.FAILED
    assert result.observations == ()


def test_report_distinguishes_positive_observations_from_complete_scope() -> None:
    complete = SynchronizationReport(
        run_id="complete",
        completeness=InventoryCompleteness.COMPLETE,
        discovered=1,
        eligible=1,
        ineligible=0,
    )
    positive_only = SynchronizationReport(
        run_id="positive-only",
        completeness=InventoryCompleteness.INCOMPLETE,
        discovered=1,
        eligible=1,
        ineligible=0,
    )
    ambiguous = SynchronizationReport(
        run_id="ambiguous",
        completeness=InventoryCompleteness.INCOMPLETE,
        discovered=1,
        eligible=1,
        ineligible=0,
        failure_code=SynchronizationFailureCode.EXTRACTION_AMBIGUOUS,
    )

    assert complete.succeeded
    assert not complete.accepted_positive_observations
    assert not positive_only.succeeded
    assert positive_only.accepted_positive_observations
    assert not ambiguous.accepted_positive_observations


def test_synchronization_preserves_inventory_terminal_diagnosis() -> None:
    diagnosis = TerminalBrowserDiagnosis(
        reason=TerminalBrowserReason.UNRESOLVED_AMBIGUITY,
        step_id=DomStepId.INVENTORY_EXTRACTION,
        provenance=DiagnosisProvenance.POLICY_STOP,
        confidence=1.0,
        evidence=frozenset(),
        operator_action=OperatorAction.MAINTAIN_CODE,
    )
    discovery = InventoryDiscoveryResult(
        observations=(),
        completeness=InventoryCompleteness.FAILED,
        failure_code=SynchronizationFailureCode.EXTRACTION_AMBIGUOUS,
        failure_detail="Inventory extraction stayed ambiguous.",
        terminal_diagnosis=diagnosis,
    )

    class Source:
        def discover(self, _browser: object) -> InventoryDiscoveryResult:
            return discovery

    class Repository:
        def reconcile(self, **_kwargs: object) -> SynchronizationReport:
            return SynchronizationReport(
                run_id="run-1",
                completeness=InventoryCompleteness.FAILED,
                discovered=0,
                eligible=0,
                ineligible=0,
                failure_code=SynchronizationFailureCode.EXTRACTION_AMBIGUOUS,
                failure_detail="Inventory extraction stayed ambiguous.",
            )

        def list_for_user(self, _user_id: int) -> list[object]:
            return []

    report = SynchronizeBookingAccount(  # type: ignore[arg-type]
        Source(),
        Repository(),
        clock=lambda: datetime(2026, 8, 13, tzinfo=UTC),
    ).execute(
        browser=object(),
        user_id=1,
        trigger=SynchronizationTrigger.BOOKINGS,
        session_revision="session-1",
    )

    assert report.terminal_diagnosis is diagnosis


def test_synchronization_preserves_positive_inventory_assistance_receipts() -> None:
    assisted = TerminalBrowserDiagnosis(
        reason=TerminalBrowserReason.POSTCONDITION_SATISFIED,
        step_id=DomStepId.INVENTORY_SCOPE,
        provenance=DiagnosisProvenance.OPUS_RECOVERED,
        confidence=0.9,
        evidence=frozenset(),
        operator_action=OperatorAction.NONE,
    )
    discovery = InventoryDiscoveryResult(
        observations=(),
        completeness=InventoryCompleteness.COMPLETE,
        assisted_diagnoses=(assisted,),
    )

    class Source:
        def discover(self, _browser: object) -> InventoryDiscoveryResult:
            return discovery

    class Repository:
        def reconcile(self, **_kwargs: object) -> SynchronizationReport:
            return SynchronizationReport(
                run_id="run-assisted",
                completeness=InventoryCompleteness.COMPLETE,
                discovered=0,
                eligible=0,
                ineligible=0,
            )

        def list_for_user(self, _user_id: int) -> list[object]:
            return []

    report = SynchronizeBookingAccount(  # type: ignore[arg-type]
        Source(),
        Repository(),
        clock=lambda: datetime(2026, 8, 13, tzinfo=UTC),
    ).execute(
        browser=object(),
        user_id=1,
        trigger=SynchronizationTrigger.BOOKINGS,
        session_revision="session-assisted",
    )

    assert report.assisted_diagnoses == (assisted,)
