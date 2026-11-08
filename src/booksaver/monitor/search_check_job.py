from __future__ import annotations

import logging
import re
from collections.abc import Callable
from datetime import UTC, datetime

from booksaver.application.browser_executor import (
    OwnerBoundAgenticPriceCheck,
    PriceExecutionOutcome,
)
from booksaver.application.ports import CheckHistoryRepository, CheckTraceRepository
from booksaver.domain.browser_executor import (
    ExecutionLimits,
    PriceExecutionStatus,
    ValidationRejection,
)
from booksaver.domain.browser_resilience import TerminalBrowserDiagnosis
from booksaver.domain.check_result import (
    CheckResult,
    ExtractedBookingFields,
    ExtractionMethod,
    FailureCode,
    FailureReason,
    RefundIndicators,
)
from booksaver.domain.meal_plan import offer_meal_plan
from booksaver.domain.mobile_web import (
    GeniusEvidence,
    MobileProfileId,
    PriceSourceProvenance,
)
from booksaver.domain.models import Booking
from booksaver.domain.offer import ExclusionReason, OfferCandidate, select_offer
from booksaver.domain.session import SessionMode
from booksaver.domain.user_session import UserSessionSnapshot
from booksaver.monitor.failure_tracker import FailureTracker
from booksaver.monitor.trace import TraceRecorder

logger = logging.getLogger(__name__)

_GENIUS_EVIDENCE = re.compile(r"\bGenius(?:\s+(?:Level|discount|deal|rate))?\b", re.I)
_ROOM_RATE_PLAN_SUFFIX = re.compile(
    r"\s*(?:-|\u2013|\u2014|\|)\s*(?:flexible(?:\s+rate)?|refundable(?:\s+rate)?|"
    r"free\s+cancellation)\s*$",
    re.IGNORECASE,
)


def _normalized_room_identity(label: str) -> str:
    normalized = " ".join(label.casefold().split())
    for _ in range(3):
        stripped = _ROOM_RATE_PLAN_SUFFIX.sub("", normalized).strip()
        if stripped == normalized:
            break
        normalized = stripped
    return normalized


class BookingComSearchMonitor:
    """Owner-bound Jev price check (ADR-056): validate, select, and persist one result."""

    def __init__(
        self,
        check_history: CheckHistoryRepository,
        failure_tracker: FailureTracker,
        trace_repo: CheckTraceRepository | None = None,
        mobile_profile_id: MobileProfileId = MobileProfileId.ANDROID_CHROMIUM,
        agentic_price_check: OwnerBoundAgenticPriceCheck | None = None,
        agentic_owner_user_id: int | None = None,
        agentic_execution_limits: ExecutionLimits | None = None,
        room_equivalence_policy: (Callable[[str, Booking], tuple[bool, float]] | None) = None,
    ) -> None:
        self._history = check_history
        self._failures = failure_tracker
        self._trace_repo = trace_repo
        self._last_llm_calls_used = 0
        self._mobile_profile_id = mobile_profile_id
        self._agentic_price_check = agentic_price_check
        self._agentic_owner_user_id = agentic_owner_user_id
        self._agentic_execution_limits = agentic_execution_limits
        self._room_equivalence_policy = room_equivalence_policy or self._qualified_room_equivalence
        self._last_agentic_outcome: PriceExecutionOutcome | None = None

    @property
    def last_llm_calls_used(self) -> int:
        """Model calls the price executor reported for the most recent check."""
        return self._last_llm_calls_used

    @property
    def last_agentic_outcome(self) -> PriceExecutionOutcome | None:
        """Ephemeral outcome for the coordinator's content-free canary projection."""
        return self._last_agentic_outcome

    def run_authenticated(self, booking: Booking, snapshot: UserSessionSnapshot) -> CheckResult:
        """Run one fail-closed owner-bound check and persist its result."""
        result = self._run_agentic_authenticated(booking, snapshot)
        self._record(result)
        return result

    def _run_agentic_authenticated(
        self,
        booking: Booking,
        snapshot: UserSessionSnapshot,
    ) -> CheckResult:
        recorder = TraceRecorder(booking.booking_id)
        self._last_llm_calls_used = 0
        self._last_agentic_outcome = None
        if self._agentic_price_check is None or self._agentic_owner_user_id is None:
            result = CheckResult.failure(
                booking.booking_id,
                datetime.now(UTC),
                FailureReason(
                    FailureCode.PROVIDER_AUTHENTICATION,
                    "Agentic routing is selected but its configured price executor is unavailable.",
                ),
            )
            self._persist_trace(recorder, result)
            return result
        try:
            outcome = self._agentic_price_check.execute(
                owner_user_id=self._agentic_owner_user_id,
                booking=booking,
                session_material=snapshot.cookies,
                limits=self._agentic_execution_limits,
            )
            self._last_agentic_outcome = outcome
            self._last_llm_calls_used = outcome.result.usage.model_calls
            result = self._agentic_check_result(
                booking,
                outcome,
                snapshot.metadata.revision_id,
                recorder,
            )
        except Exception as exc:
            logger.error(
                "Unexpected agentic execution error for booking %s failure_type=%s",
                booking.booking_id,
                type(exc).__name__,
            )
            result = CheckResult.failure(
                booking.booking_id,
                datetime.now(UTC),
                FailureReason(
                    FailureCode.INFRASTRUCTURE_FAILURE,
                    f"Agentic browser check stopped after {type(exc).__name__}.",
                ),
            )
        self._persist_trace(recorder, result)
        return result

    def _agentic_check_result(
        self,
        booking: Booking,
        outcome: PriceExecutionOutcome,
        session_revision_id: str,
        recorder: TraceRecorder | None = None,
    ) -> CheckResult:
        now = datetime.now(UTC)
        if not outcome.validation.accepted:
            if recorder is not None:
                recorder.price_validation(booking, outcome, (), None, _normalized_room_identity)
            code = self._agentic_failure_code(
                outcome.result.status,
                outcome.validation.rejection,
            )
            rejection = (
                outcome.validation.rejection.value
                if outcome.validation.rejection is not None
                else outcome.result.status.value
            )
            return CheckResult.failure(
                booking.booking_id,
                now,
                FailureReason(
                    code,
                    "The property shows no availability for these dates."
                    if outcome.result.status is PriceExecutionStatus.UNAVAILABLE
                    else "This check could not verify a matching offer: "
                    f"{rejection}. See the check trace for evidence rejection reasons.",
                ),
            )

        candidates: list[OfferCandidate] = []
        for offer in outcome.validation.accepted_offers:
            matches, confidence = self._room_equivalence_policy(
                offer.room_label,
                booking,
            )
            candidates.append(
                OfferCandidate(
                    room_label=offer.room_label,
                    total=offer.total,
                    is_refundable=True,
                    cancellation_text=offer.cancellation_text,
                    matches_room=matches,
                    match_confidence=confidence,
                    meal_plan=offer_meal_plan(offer.meal_text),
                )
            )
        selection = select_offer(candidates, booking)
        if recorder is not None:
            recorder.price_validation(
                booking, outcome, candidates, selection, _normalized_room_identity,
            )
        if selection.chosen is None:
            return CheckResult.failure(
                booking.booking_id,
                now,
                FailureReason(
                    FailureCode.NO_EQUIVALENT_OFFER,
                    (
                        "No matching room type found"
                        if selection.excluded
                        and all(
                            reason is ExclusionReason.ROOM_MISMATCH
                            for _, reason in selection.excluded
                        )
                        else "No equivalent offer found"
                    )
                    + f": {len(candidates)} prices found; {selection.exclusion_summary()}.",
                ),
            )
        facts = outcome.result.query_facts
        genius = (
            GeniusEvidence.APPLIED_OR_PRESENT
            if facts is not None and facts.genius is True
            else GeniusEvidence.NOT_OBSERVED
        )
        return self._to_success(
            booking,
            selection.chosen,
            (ExtractionMethod.AGENT if outcome.result.fallback_used else ExtractionMethod.LLM),
            now,
            session_mode=SessionMode.AUTHENTICATED,
            session_revision_id=session_revision_id,
            genius_evidence=genius,
        )

    @staticmethod
    def _qualified_room_equivalence(
        observed_room_label: str,
        booking: Booking,
    ) -> tuple[bool, float]:
        observed = " ".join(observed_room_label.casefold().split())
        booked = " ".join(booking.room_type.label.casefold().split())
        if observed == booked:
            return True, 1.0
        qualified = _normalized_room_identity(observed_room_label) == booked
        return qualified, 0.95 if qualified else 0.0

    @staticmethod
    def _agentic_failure_code(
        status: PriceExecutionStatus,
        rejection: ValidationRejection | None,
    ) -> FailureCode:
        rejection_codes = {
            ValidationRejection.PROPERTY_MISMATCH: FailureCode.PROPERTY_NOT_FOUND,
            ValidationRejection.DATE_MISMATCH: FailureCode.STEP_FAILED,
            ValidationRejection.OCCUPANCY_MISMATCH: FailureCode.OCCUPANCY_MISSING,
            ValidationRejection.AUTHENTICATION_REQUIRED: FailureCode.AUTH_REQUIRED,
            ValidationRejection.CURRENCY_MISMATCH: FailureCode.CURRENCY_MISMATCH,
            ValidationRejection.NO_COMPLETE_REFUNDABLE_ALL_IN_OFFER: (
                FailureCode.NO_EQUIVALENT_OFFER
            ),
            ValidationRejection.EXECUTION_LIMIT_BREACH: FailureCode.BUDGET_EXCEEDED,
            ValidationRejection.QUERY_EVIDENCE_INCOMPLETE: FailureCode.EXTRACTION_FAILED,
        }
        if rejection in rejection_codes:
            return rejection_codes[rejection]
        return {
            PriceExecutionStatus.SESSION_UNAVAILABLE: FailureCode.AUTH_REQUIRED,
            PriceExecutionStatus.SIGNED_OUT: FailureCode.AUTH_REQUIRED,
            PriceExecutionStatus.MFA_REQUIRED: FailureCode.AUTH_REQUIRED,
            PriceExecutionStatus.CAPTCHA: FailureCode.BOT_WALL,
            PriceExecutionStatus.BOT_WALL: FailureCode.BOT_WALL,
            PriceExecutionStatus.UNAVAILABLE: FailureCode.NO_EQUIVALENT_OFFER,
            PriceExecutionStatus.UNSAFE_ACTION: FailureCode.BLOCKED_ACTION,
            PriceExecutionStatus.PROVIDER_FAILURE: FailureCode.PROVIDER_UNAVAILABLE,
            PriceExecutionStatus.BUDGET_EXHAUSTED: FailureCode.BUDGET_EXCEEDED,
            PriceExecutionStatus.TIMEOUT: FailureCode.TIMEOUT,
            PriceExecutionStatus.NO_VALID_OBSERVATION: FailureCode.EXTRACTION_FAILED,
        }.get(status, FailureCode.EXTRACTION_FAILED)

    def _persist_trace(self, recorder: TraceRecorder, result: CheckResult) -> None:
        if self._trace_repo is not None:
            try:
                self._trace_repo.add(recorder.finish(result))
            except Exception as exc:
                logger.warning("Could not persist check trace: %s", exc)

    def _to_success(
        self,
        booking: Booking,
        chosen: OfferCandidate,
        method: ExtractionMethod,
        now: datetime,
        session_mode: SessionMode = SessionMode.AUTHENTICATED,
        session_revision_id: str | None = None,
        page_text: str = "",
        assisted_diagnoses: tuple[TerminalBrowserDiagnosis, ...] = (),
        genius_evidence: GeniusEvidence | None = None,
    ) -> CheckResult:
        """Map the chosen candidate to the downstream CheckResult contract.

        Property and dates were verified by the journey, so they are reported as
        the booking's own (verified-equal) values. A drift-matched room label is
        reported as None — absence passes the US-008 gate, whereas echoing the
        differing label would wrongly reject the already-judged equivalence.
        """
        if not chosen.exact_label_match(booking):
            logger.info(
                "Room match via judgment (confidence %.2f): booked %r ~ offered %r",
                chosen.match_confidence,
                booking.room_type.label,
                chosen.room_label,
            )
        price_source = None
        if session_revision_id is not None:
            genius = genius_evidence or (
                GeniusEvidence.APPLIED_OR_PRESENT
                if _GENIUS_EVIDENCE.search(page_text)
                else GeniusEvidence.NOT_OBSERVED
            )
            price_source = PriceSourceProvenance(
                profile_id=self._mobile_profile_id,
                session_revision_id=session_revision_id,
                genius_evidence=genius,
                observed_at=now,
            )
        return CheckResult.success(
            booking_id=booking.booking_id,
            checked_at=now,
            live_price=chosen.total,
            extraction_method=method,
            refund_indicators=RefundIndicators(
                is_refundable=chosen.is_refundable,
                raw_text=chosen.cancellation_text,
            ),
            extracted_fields=ExtractedBookingFields(
                property_name=booking.property.name,
                room_label=chosen.room_label if chosen.exact_label_match(booking) else None,
                check_in=booking.stay_dates.check_in,
                check_out=booking.stay_dates.check_out,
            ),
            session_mode=session_mode,
            price_source=price_source,
            assisted_diagnoses=assisted_diagnoses,
            offer_meal_plan=chosen.meal_plan,
        )

    def _record(self, result: CheckResult) -> None:
        self._history.add(result)
        self._failures.after_check(result.booking_id, succeeded=result.outcome.value == "success")
