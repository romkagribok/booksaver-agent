from __future__ import annotations

import logging
from datetime import UTC, datetime

from booksaver.application.ports import (
    BookingRepository,
    BrowserSession,
    CheckHistoryRepository,
    ExtractionResult,
    LLMExtractor,
    PageContent,
)
from booksaver.domain.check_result import (
    CheckResult,
    ExtractionMethod,
    FailureCode,
    FailureReason,
    RefundIndicators,
)
from booksaver.domain.models import Booking
from booksaver.monitor import dom_extract
from booksaver.monitor.failure_tracker import FailureTracker
from booksaver.monitor.session_manager import SessionManager

logger = logging.getLogger(__name__)

_CONFIDENCE_THRESHOLD = 0.5

_MANAGE_URL = "https://secure.booking.com/myreservations.html"


def booking_url(booking: Booking) -> str:
    """Manage-page URL for a booking; uses the stored ref when it is a full URL."""
    ref = booking.property.booking_com_ref
    if ref.startswith("http://") or ref.startswith("https://"):
        return ref
    return _MANAGE_URL


class BookingComMonitor:
    def __init__(
        self,
        browser: BrowserSession,
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

    def run_all_active(self) -> list[CheckResult]:
        """Scheduler job entry point: check every active booking, never raise."""
        results: list[CheckResult] = []
        bookings = self._bookings.list_active()
        if not bookings:
            logger.info("No active bookings to check")
            return results

        session = self._sessions.ensure_active()
        if session is None:
            # Reauth needed — record a failure per booking so history shows the gap
            now = datetime.now(UTC)
            reason = FailureReason(
                code=FailureCode.AUTH_REQUIRED,
                detail="No active Booking.com session. Run 'booksaver auth'.",
            )
            for booking in bookings:
                result = CheckResult.failure(booking.booking_id, now, reason)
                self._history.add(result)
                self._failures.after_check(booking.booking_id, succeeded=False)
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
            self._history.add(result)
            self._failures.after_check(
                booking.booking_id, succeeded=result.outcome.value == "success"
            )
            results.append(result)
            if (
                not reauth_flagged
                and result.failure_reason is not None
                and result.failure_reason.code is FailureCode.AUTH_REQUIRED
            ):
                self._sessions.mark_reauth_required(session)
                reauth_flagged = True

        if not reauth_flagged and self._browser.is_authenticated():
            try:
                self._sessions.save_refreshed(session, self._browser.get_cookies())
            except Exception as exc:
                logger.warning("Could not save refreshed cookies: %s", exc)

        return results

    def run_check(self, booking: Booking) -> CheckResult:
        """Check one booking. Always returns a CheckResult; never raises."""
        now = datetime.now(UTC)
        url = booking_url(booking)

        try:
            page = self._browser.open_page(url)
        except Exception as exc:
            logger.error("Navigation failed for booking %s: %s", booking.booking_id, exc)
            return CheckResult.failure(
                booking.booking_id,
                now,
                FailureReason(code=FailureCode.NAVIGATION_ERROR, detail=str(exc)),
            )

        if not self._browser.is_authenticated():
            return CheckResult.failure(
                booking.booking_id,
                now,
                FailureReason(
                    code=FailureCode.AUTH_REQUIRED,
                    detail="Page indicates the session is not authenticated.",
                ),
            )

        # DOM first, LLM fallback (US-006)
        extraction = dom_extract.extract_from_text(page.text)
        method = ExtractionMethod.DOM

        if extraction.price is None or extraction.confidence < _CONFIDENCE_THRESHOLD:
            llm_extraction = self._try_llm(page, booking)
            if llm_extraction is not None:
                extraction = llm_extraction
                method = ExtractionMethod.LLM

        if extraction.price is None or extraction.confidence < _CONFIDENCE_THRESHOLD:
            return CheckResult.failure(
                booking.booking_id,
                now,
                FailureReason(
                    code=FailureCode.EXTRACTION_FAILED,
                    detail="Neither DOM nor LLM extraction produced a confident price.",
                ),
            )

        return CheckResult.success(
            booking_id=booking.booking_id,
            checked_at=now,
            live_price=extraction.price,
            extraction_method=method,
            refund_indicators=RefundIndicators(
                is_refundable=extraction.is_refundable,
                raw_text=extraction.cancellation_deadline_raw,
            ),
        )

    def _try_llm(self, page: PageContent, booking: Booking) -> ExtractionResult | None:
        if self._llm is None:
            logger.info("LLM extractor not configured; DOM-only mode")
            return None
        try:
            return self._llm.extract_price(page.text, booking)
        except Exception as exc:
            logger.error("LLM extraction failed for booking %s: %s", booking.booking_id, exc)
            return None
