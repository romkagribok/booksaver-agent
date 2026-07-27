from datetime import UTC, date, datetime

from booksaver.domain.account_sync import (
    EligibilityReason,
    InventoryCompleteness,
    InventoryDiscoveryResult,
    ReservationLifecycle,
    ReservationObservation,
    SynchronizationFailureCode,
    evaluate_eligibility,
    remote_key_hash,
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
