from __future__ import annotations

import logging
from datetime import UTC, datetime

from booksaver.application.ports import (
    BookingRepository,
    CheckHistoryRepository,
    InteractiveBrowser,
    LLMExtractor,
)
from booksaver.domain.check_result import (
    CheckResult,
    ExtractedBookingFields,
    ExtractionMethod,
    FailureCode,
    FailureReason,
    RefundIndicators,
)
from booksaver.domain.models import Booking
from booksaver.domain.offer import OfferCandidate, select_offer
from booksaver.monitor import room_table
from booksaver.monitor.failure_tracker import FailureTracker
from booksaver.monitor.search_journey import SearchJourney
from booksaver.monitor.session_manager import SessionManager

logger = logging.getLogger(__name__)


class BookingComSearchMonitor:
    """Search-flow price monitor (ADR-013): replaces the manage-page monitor as
    the sole producer of live prices. Same never-raise contract and session
    handling as bolt 003's BookingComMonitor.
    """

    def __init__(
        self,
        browser: InteractiveBrowser,
        session_manager: SessionManager,
        check_history: CheckHistoryRepository,
        booking_repo: BookingRepository,
        failure_tracker: FailureTracker,
        llm: LLMExtractor | None = None,
    ) -> None:
        self._browser = browser
        self._sessions = session_manager
        self._history = check_history
        self._bookings = booking_repo
        self._failures = failure_tracker
        self._llm = llm
        self._journey = SearchJourney(browser)

    def run_all_active(self) -> list[CheckResult]:
        """Scheduler job entry point: check every active booking, never raise."""
        results: list[CheckResult] = []
        bookings = self._bookings.list_active()
        if not bookings:
            logger.info("No active bookings to check")
            return results

        session = self._sessions.ensure_active()
        if session is None:
            now = datetime.now(UTC)
            reason = FailureReason(
                code=FailureCode.AUTH_REQUIRED,
                detail="No active Booking.com session. Run 'booksaver auth'.",
            )
            for booking in bookings:
                result = CheckResult.failure(booking.booking_id, now, reason)
                self._record(result)
                results.append(result)
            return results

        try:
            self._browser.restore_cookies(session.cookies)
        except Exception as exc:
            logger.error("Failed to restore session cookies: %s", exc)
            self._sessions.mark_reauth_required(session)
            return results

        reauth_flagged = False
        for booking in bookings:
            result = self.run_check(booking)
            self._record(result)
            results.append(result)
            if (
                not reauth_flagged
                and result.failure_reason is not None
                and result.failure_reason.code is FailureCode.AUTH_REQUIRED
            ):
                self._sessions.mark_reauth_required(session)
                reauth_flagged = True

        try:
            self._sessions.save_refreshed(session, self._browser.get_cookies())
        except Exception as exc:
            logger.warning("Could not save refreshed cookies: %s", exc)

        return results

    def run_check(self, booking: Booking) -> CheckResult:
        """Check one booking via the search journey. Always returns; never raises."""
        now = datetime.now(UTC)

        if booking.occupancy is None:
            return CheckResult.failure(
                booking.booking_id,
                now,
                FailureReason(
                    code=FailureCode.OCCUPANCY_MISSING,
                    detail=(
                        "Booking predates the occupancy field. Run: booksaver bookings "
                        f"set-occupancy {booking.booking_id} --adults N"
                    ),
                ),
            )

        journey = self._journey.run(booking)
        if not journey.ok:
            failed = journey.failed_step
            assert failed is not None and journey.failure_code is not None
            return CheckResult.failure(
                booking.booking_id,
                now,
                FailureReason(
                    code=journey.failure_code,
                    detail=f"step={failed.step.value}: {failed.detail}",
                ),
            )

        try:
            page_text = self._browser.snapshot().text
        except Exception as exc:
            return CheckResult.failure(
                booking.booking_id,
                now,
                FailureReason(code=FailureCode.NAVIGATION_ERROR, detail=str(exc)),
            )

        candidates = room_table.parse_candidates(page_text, booking)
        method = ExtractionMethod.DOM
        if not room_table.has_confident_exact_match(candidates, booking):
            llm_candidates = self._try_llm_offers(page_text, booking)
            if llm_candidates is not None:
                candidates = llm_candidates
                method = ExtractionMethod.LLM

        if not candidates:
            return CheckResult.failure(
                booking.booking_id,
                now,
                FailureReason(
                    code=FailureCode.EXTRACTION_FAILED,
                    detail="No offers could be parsed from the room table.",
                ),
            )

        selection = select_offer(candidates, booking)
        if selection.chosen is None:
            return CheckResult.failure(
                booking.booking_id,
                now,
                FailureReason(
                    code=FailureCode.NO_EQUIVALENT_OFFER,
                    detail=(
                        f"{len(candidates)} offers parsed, none equivalent+refundable "
                        f"(excluded: {selection.exclusion_summary()})"
                    ),
                ),
            )

        return self._to_success(booking, selection.chosen, method, now)

    def _to_success(
        self,
        booking: Booking,
        chosen: OfferCandidate,
        method: ExtractionMethod,
        now: datetime,
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
        )

    def _try_llm_offers(
        self, page_text: str, booking: Booking
    ) -> list[OfferCandidate] | None:
        if self._llm is None:
            logger.info("LLM extractor not configured; DOM-only offer parsing")
            return None
        try:
            return self._llm.extract_offers(page_text, booking)
        except Exception as exc:
            logger.error(
                "LLM offer extraction failed for booking %s: %s", booking.booking_id, exc
            )
            return None

    def _record(self, result: CheckResult) -> None:
        self._history.add(result)
        self._failures.after_check(
            result.booking_id, succeeded=result.outcome.value == "success"
        )
