import json
from dataclasses import replace
from decimal import Decimal
from unittest.mock import Mock

import pytest

from booksaver.application.browser_executor import PriceExecutionOutcome
from booksaver.domain.agent import TraceKind
from booksaver.domain.browser_executor import (
    AllInEvidence,
    EvidenceCompleteness,
    ObservedOffer,
    PriceExecutionStatus,
    PriceObservationValidation,
    RefundabilityEvidence,
    ValidatedObservedOffer,
    ValidationRejection,
    observed_offer_rejection_reasons,
)
from booksaver.domain.check_result import CheckOutcome, FailureCode
from booksaver.domain.value_objects import Money
from booksaver.monitor.failure_tracker import FailureTracker
from booksaver.monitor.search_check_job import BookingComSearchMonitor

from .fakes import (
    FakeCheckHistoryRepository,
    FakeCheckTraceRepository,
    make_booking,
)
from .test_agentic_search_check_job import _AgenticCheck, _outcome, _snapshot


def _with_offers(offers: tuple[ObservedOffer, ...]) -> PriceExecutionOutcome:
    base = _outcome()
    accepted = tuple(
        ValidatedObservedOffer(offer.room_label, offer.total, offer.refundability_text or "")
        for offer in offers
        if not observed_offer_rejection_reasons(offer, "EUR")
    )
    return PriceExecutionOutcome(
        replace(base.result, offers=offers),
        PriceObservationValidation(
            accepted_offers=accepted,
            rejected_offer_count=len(offers) - len(accepted),
            rejection=None if accepted else ValidationRejection.NO_COMPLETE_REFUNDABLE_ALL_IN_OFFER,
        ),
    )


def _run(
    outcome: PriceExecutionOutcome,
    *,
    policy: Mock | None = None,
    expect_diagnostic: bool = True,
):
    traces = FakeCheckTraceRepository()
    history = FakeCheckHistoryRepository()
    monitor = BookingComSearchMonitor(
        check_history=history,
        failure_tracker=FailureTracker(history),
        trace_repo=traces,
        agentic_price_check=_AgenticCheck(outcome),  # type: ignore[arg-type]
        agentic_owner_user_id=7,
        room_equivalence_policy=policy,
    )
    result = monitor.run_authenticated(make_booking(), _snapshot())
    [trace] = traces.traces
    events = [event for event in trace.events if event.kind is TraceKind.PRICE_VALIDATION]
    assert trace.check_id == result.check_id
    assert history.results == [result]
    if expect_diagnostic:
        [event] = events
        return result, json.loads(event.detail), trace
    assert events == []
    return result, {}, trace


@pytest.mark.parametrize(
    ("label", "expected_outcome", "comparison", "selection"),
    [
        ("Standard Double", CheckOutcome.SUCCESS, "matched", "selected"),
        ("Standard Double - Flexible", CheckOutcome.SUCCESS, "matched", "selected"),
        ("Deluxe King Suite", CheckOutcome.FAILURE, "mismatched", "room_mismatch"),
    ],
)
def test_monitor_persists_actual_room_and_selection_decisions(
    label, expected_outcome, comparison, selection,
) -> None:
    result, payload, _trace = _run(_outcome(room_label=label))
    assert result.outcome is expected_outcome
    assert payload["version"] == "price-validation-v1"
    assert payload["observed_offer_count"] == payload["evidence_accepted_count"] == 1
    assert payload["evidence_rejected_count"] == 0
    [offer] = payload["offers"]
    assert offer["evidence_rejections"] == []
    assert offer["room_comparison"] == comparison
    assert offer["selection"] == selection
    assert offer["observed_suffix_removed"] is (label == "Standard Double - Flexible")
    if expected_outcome is CheckOutcome.SUCCESS:
        assert result.live_price == Money(Decimal("350"), "EUR")
    else:
        assert result.failure_reason.code is FailureCode.NO_EQUIVALENT_OFFER


def test_provider_failure_persists_diagnostic_without_room_evaluation() -> None:
    policy = Mock(side_effect=AssertionError("must not evaluate a provider failure"))
    result, payload, _trace = _run(
        _outcome(status=PriceExecutionStatus.PROVIDER_FAILURE), policy=policy,
    )
    assert result.failure_reason.code is FailureCode.PROVIDER_UNAVAILABLE
    assert payload["executor_status"] == "provider_failure"
    assert payload["query_or_evidence_rejection"] == "execution_not_observed"
    assert payload["offers"] == []
    assert payload["room_evaluated_count"] == 0
    policy.assert_not_called()


def test_query_failure_marks_room_and_selection_not_evaluated() -> None:
    base = _outcome()
    outcome = PriceExecutionOutcome(
        base.result,
        PriceObservationValidation(rejection=ValidationRejection.DATE_MISMATCH),
    )
    policy = Mock(side_effect=AssertionError("must not evaluate a mismatched query"))
    result, payload, _trace = _run(outcome, policy=policy)
    assert result.outcome is CheckOutcome.FAILURE
    assert payload["query_or_evidence_rejection"] == "date_mismatch"
    [offer] = payload["offers"]
    assert offer["evidence_rejections"] == []
    assert offer["room_comparison"] == offer["selection"] == "not_evaluated"
    assert payload["room_evaluated_count"] == 0
    policy.assert_not_called()


def test_multiple_failed_gates_are_persisted_together() -> None:
    offer = replace(
        _outcome().result.offers[0],
        completeness=EvidenceCompleteness.INCOMPLETE,
        all_in=AllInEvidence.UNKNOWN,
        refundability=RefundabilityEvidence.UNKNOWN,
        refundability_text=None,
        total=Money(Decimal("350"), "USD"),
    )
    result, payload, _trace = _run(_with_offers((offer,)))
    assert result.outcome is CheckOutcome.FAILURE
    assert payload["evidence_rejected_count"] == 1
    [record] = payload["offers"]
    assert record["evidence_rejections"] == [
        "incomplete_evidence", "all_in_not_explicit", "refundability_not_explicit",
        "refundability_text_missing", "currency_mismatch",
    ]
    assert record["refundability_text_present"] is False
    assert record["room_comparison"] == record["selection"] == "not_evaluated"


def test_hostile_observed_content_is_absent_from_persisted_trace() -> None:
    offer = replace(
        _outcome().result.offers[0],
        room_label="Deluxe King attacker@example.org https://evil.invalid sk-ant-secret-123",
        refundability_text=(
            "Free cancellation. cookie=privatecookie confirmation=secretconfirmation"
        ),
    )
    _result, payload, trace = _run(_with_offers((offer,)))
    serialized = " ".join(event.detail for event in trace.events)
    for forbidden in (
        offer.room_label, offer.refundability_text, "attacker", "example.org", "evil.invalid",
        "sk-ant-secret", "privatecookie", "secretconfirmation",
    ):
        assert forbidden not in serialized
    hints = payload["offers"][0]["observed_room_hints"]
    assert hints["recognized_words"] == ["deluxe", "king"]
    assert hints["other_word_count"] > 0


def test_offer_details_are_bounded_but_totals_and_matching_cover_all_offers() -> None:
    offer = _outcome().result.offers[0]
    offers = tuple(replace(offer, total=Money(Decimal(350 - index), "EUR")) for index in range(25))
    policy = Mock(return_value=(True, 1.0))
    result, payload, _trace = _run(_with_offers(offers), policy=policy)
    assert result.outcome is CheckOutcome.SUCCESS
    assert result.live_price == Money(Decimal("326"), "EUR")
    assert len(payload["offers"]) == 20
    assert payload["omitted_offer_count"] == 5
    assert payload["observed_offer_count"] == payload["room_evaluated_count"] == 25
    assert payload["room_matched_count"] == 25
    assert payload["selected"] is True
    assert policy.call_count == 25
    assert all(item["selection"] == "eligible_not_selected" for item in payload["offers"])


def test_diagnostics_use_actual_policy_result_once_per_accepted_offer() -> None:
    valid = _outcome().result.offers[0]
    invalid = replace(valid, all_in=AllInEvidence.UNKNOWN)
    # Stateful policy catches a diagnostic implementation which repeats matching.
    policy = Mock(side_effect=[(False, 0.0), (True, 1.0)])
    result, payload, _trace = _run(_with_offers((valid, invalid, valid)), policy=policy)
    assert result.outcome is CheckOutcome.SUCCESS
    assert policy.call_count == 2
    assert [item["room_comparison"] for item in payload["offers"]] == [
        "mismatched", "not_evaluated", "matched",
    ]
    assert [item["selection"] for item in payload["offers"]] == [
        "room_mismatch", "not_evaluated", "selected",
    ]


def test_diagnostic_builder_failure_does_not_change_success(monkeypatch, caplog) -> None:
    monkeypatch.setattr(
        "booksaver.monitor.trace.price_validation_diagnostics",
        Mock(side_effect=RuntimeError("sensitive observed text")),
    )
    result, _payload, trace = _run(_outcome(), expect_diagnostic=False)
    assert result.outcome is CheckOutcome.SUCCESS
    assert result.live_price == Money(Decimal("350"), "EUR")
    assert any(event.kind is TraceKind.CHECK_RESULT for event in trace.events)
    assert "diagnostics unavailable: RuntimeError" in caplog.text
    assert "sensitive observed text" not in caplog.text
