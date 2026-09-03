from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from booksaver.application.browser_executor import PriceExecutionOutcome
from booksaver.domain.browser_executor import (
    AllInEvidence,
    EvidenceCompleteness,
    ExecutionUsage,
    ObservationSource,
    ObservedOffer,
    ObservedQueryFacts,
    PriceExecutionResult,
    PriceExecutionStatus,
    PriceObservationValidation,
    RedactedProvenance,
    RefundabilityEvidence,
    RoutingDecision,
    RoutingReason,
    ValidatedObservedOffer,
    ValidationRejection,
)
from booksaver.domain.check_result import CheckOutcome, ExtractionMethod, FailureCode
from booksaver.domain.user_session import UserSessionMetadata, UserSessionSnapshot
from booksaver.domain.value_objects import Money, Platform
from booksaver.monitor.failure_tracker import FailureTracker
from booksaver.monitor.search_check_job import BookingComSearchMonitor
from booksaver.monitor.session_manager import SessionManager

from .fakes import (
    FakeBookingRepository,
    FakeCheckHistoryRepository,
    FakeInteractiveBrowser,
    FakeSessionRepository,
    make_booking,
    make_session,
)


def _snapshot() -> UserSessionSnapshot:
    return UserSessionSnapshot(
        UserSessionMetadata.imported(
            owner_user_id=7,
            platform=Platform.BOOKING_COM,
            imported_at=datetime.now(UTC),
            expires_at=None,
        ),
        b"owner-cookie-material",
    )


def _outcome(
    *,
    room_label: str = "Standard Double",
    fallback: bool = False,
    status: PriceExecutionStatus = PriceExecutionStatus.OBSERVED,
    rejection: ValidationRejection | None = None,
) -> PriceExecutionOutcome:
    booking = make_booking()
    if status is not PriceExecutionStatus.OBSERVED:
        result = PriceExecutionResult(
            status,
            usage=ExecutionUsage(model_calls=1),
            fallback_used=fallback,
        )
        return PriceExecutionOutcome(
            result,
            PriceObservationValidation(
                rejection=rejection or ValidationRejection.EXECUTION_NOT_OBSERVED
            ),
        )
    offer = ObservedOffer(
        room_label,
        Money(Decimal("350"), "EUR"),
        AllInEvidence.EXPLICIT,
        RefundabilityEvidence.EXPLICIT_REFUNDABLE,
        "Free cancellation until 30 August",
        EvidenceCompleteness.COMPLETE,
    )
    result = PriceExecutionResult(
        status,
        query_facts=ObservedQueryFacts(
            property_name=booking.property.name,
            property_reference=booking.property.booking_com_ref,
            check_in=booking.stay_dates.check_in,
            check_out=booking.stay_dates.check_out,
            occupancy=booking.occupancy,
            currency="EUR",
            authenticated=True,
            genius=True,
            completeness=EvidenceCompleteness.COMPLETE,
        ),
        offers=(offer,),
        provenance=RedactedProvenance(
            ObservationSource.COMPUTER_USE_SUBMISSION
            if fallback
            else ObservationSource.STAGEHAND_EXTRACT,
            action_count=2,
            evidence_item_count=15,
        ),
        usage=ExecutionUsage(
            model_calls=3,
            total_actions=2,
            computer_use_actions=1 if fallback else 0,
        ),
        fallback_used=fallback,
    )
    return PriceExecutionOutcome(
        result,
        PriceObservationValidation(
            accepted_offers=(
                ValidatedObservedOffer(
                    room_label,
                    offer.total,
                    offer.refundability_text or "",
                ),
            )
        ),
    )


class _AgenticCheck:
    def __init__(self, outcome: PriceExecutionOutcome) -> None:
        self.outcome = outcome
        self.calls = []

    def execute(self, **kwargs):
        self.calls.append(kwargs)
        return self.outcome


def _monitor(check: _AgenticCheck):
    browser = FakeInteractiveBrowser()
    history = FakeCheckHistoryRepository()
    monitor = BookingComSearchMonitor(
        browser=browser,
        session_manager=SessionManager(FakeSessionRepository(make_session())),
        check_history=history,
        booking_repo=FakeBookingRepository([]),
        failure_tracker=FailureTracker(history),
        agentic_price_check=check,  # type: ignore[arg-type]
        agentic_owner_user_id=7,
        agentic_route=RoutingDecision(True, RoutingReason.OWNER_CANARY),
    )
    return monitor, browser, history


def test_agentic_path_bypasses_legacy_dom_and_reuses_booksaver_result_contract() -> None:
    check = _AgenticCheck(_outcome())
    monitor, browser, history = _monitor(check)
    snapshot = _snapshot()

    result = monitor.run_authenticated(make_booking(), snapshot)

    assert result.outcome is CheckOutcome.SUCCESS
    assert result.extraction_method is ExtractionMethod.LLM
    assert result.live_price == Money(Decimal("350"), "EUR")
    assert result.price_source is not None
    assert result.price_source.genius_evidence.value == "applied_or_present"
    assert browser.actions == []
    assert browser.restored_cookies == []
    assert check.calls[0]["session_material"] == snapshot.cookies
    assert history.results == [result]
    assert monitor.last_llm_calls_used == 3


def test_computer_use_source_is_marked_agent_without_giving_it_equivalence_authority() -> None:
    check = _AgenticCheck(_outcome(room_label="Different Suite", fallback=True))
    monitor, _browser, _history = _monitor(check)

    result = monitor.run_authenticated(make_booking(), _snapshot())

    assert result.outcome is CheckOutcome.FAILURE
    assert result.failure_reason is not None
    assert result.failure_reason.code is FailureCode.NO_EQUIVALENT_OFFER


def test_qualified_room_equivalence_ignores_only_rate_plan_suffix() -> None:
    check = _AgenticCheck(_outcome(room_label="Standard Double - Flexible"))
    monitor, _browser, _history = _monitor(check)

    result = monitor.run_authenticated(make_booking(), _snapshot())

    assert result.outcome is CheckOutcome.SUCCESS


def test_qualified_room_equivalence_preserves_room_variant_boundaries() -> None:
    for room_label in (
        "Standard Twin Room - Flexible",
        "Standard Double - Hearing Accessible - Flexible",
        "Deluxe Double - Flexible",
    ):
        check = _AgenticCheck(_outcome(room_label=room_label))
        monitor, _browser, _history = _monitor(check)

        result = monitor.run_authenticated(make_booking(), _snapshot())

        assert result.outcome is CheckOutcome.FAILURE
        assert result.failure_reason is not None
        assert result.failure_reason.code is FailureCode.NO_EQUIVALENT_OFFER


def test_agentic_provider_failure_is_terminal_without_legacy_retry() -> None:
    check = _AgenticCheck(_outcome(status=PriceExecutionStatus.PROVIDER_FAILURE))
    monitor, browser, _history = _monitor(check)

    result = monitor.run_authenticated(make_booking(), _snapshot())

    assert result.failure_reason is not None
    assert result.failure_reason.code is FailureCode.PROVIDER_UNAVAILABLE
    assert browser.actions == []
    assert browser.restored_cookies == []
