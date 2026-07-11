from __future__ import annotations

import logging
import time
from collections.abc import Callable
from datetime import UTC, datetime

from booksaver.application.ports import (
    AgentBrain,
    BookingRepository,
    CheckHistoryRepository,
    CheckTraceRepository,
    InteractiveBrowser,
    LLMClientFactory,
    LLMExtractor,
)
from booksaver.domain.agent import AgentBudget, AgentSettings, BudgetExceeded
from booksaver.domain.check_result import (
    CheckResult,
    ExtractedBookingFields,
    ExtractionMethod,
    FailureCode,
    FailureReason,
    RefundIndicators,
)
from booksaver.domain.errors import UserKeyInvalidError
from booksaver.domain.models import Booking
from booksaver.domain.offer import OfferCandidate, select_offer
from booksaver.domain.session import SessionMode
from booksaver.monitor import room_table
from booksaver.monitor.browser_agent import BrowserAgent
from booksaver.monitor.failure_tracker import FailureTracker
from booksaver.monitor.search_journey import SearchJourney
from booksaver.monitor.session_manager import SessionManager
from booksaver.monitor.trace import SnapshotWriter, TraceRecorder

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
        brain: AgentBrain | None = None,
        llm_factory: LLMClientFactory | None = None,
        agent_settings: AgentSettings | None = None,
        trace_repo: CheckTraceRepository | None = None,
        snapshot_writer: SnapshotWriter | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._browser = browser
        self._sessions = session_manager
        self._history = check_history
        self._bookings = booking_repo
        self._failures = failure_tracker
        self._llm = llm
        self._brain = brain
        # US-027 hybrid billing: when set, `_run_check_inner` re-resolves
        # `self._llm`/`self._brain` per booking (owner key or the booking
        # owner's personal key) instead of using the constructor-injected
        # `llm`/`brain` for every booking. `llm`/`brain` above remain the
        # values used when no factory is supplied (every existing caller/test
        # is unaffected).
        self._llm_factory = llm_factory
        self._agent_settings = agent_settings or AgentSettings()
        self._trace_repo = trace_repo
        self._snapshots = snapshot_writer
        self._clock = clock
        self._last_escalator: BrowserAgent | None = None

    def run_all_active(self, bookings: list[Booking] | None = None) -> list[CheckResult]:
        """Scheduler job entry point: check every active booking, never raise.

        `bookings` defaults to every active booking (`self._bookings.list_active()`,
        pre-US-031 behavior). A caller doing per-user fair scheduling / daily
        check caps (US-031) instead computes its own ordered subset (e.g. via
        `monitor.user_limits.build_check_plan`) and passes it here.
        """
        results: list[CheckResult] = []
        bookings = self._bookings.list_active() if bookings is None else bookings
        if not bookings:
            logger.info("No active bookings to check")
            return results

        session = self._sessions.ensure_active()
        if session is None:
            # No usable session on this deployment (typical on a display-less
            # VPS, where headed `booksaver auth` cannot run): fall back to
            # logged-out mode rather than failing every booking (US-035,
            # FR-8). The search journey works unauthenticated and returns
            # real public bookable totals.
            mode = SessionMode.LOGGED_OUT
            logger.info(
                "No active Booking.com session — running %d booking(s) logged out "
                "(public prices).",
                len(bookings),
            )
        else:
            mode = SessionMode.AUTHENTICATED
            try:
                self._browser.restore_cookies(session.cookies)
            except Exception as exc:
                logger.error("Failed to restore session cookies: %s", exc)
                self._sessions.mark_reauth_required(session)
                return results

        reauth_flagged = False
        for booking in bookings:
            result = self.run_check(booking, session_mode=mode)
            self._record(result)
            results.append(result)
            if (
                session is not None
                and not reauth_flagged
                and result.failure_reason is not None
                and result.failure_reason.code is FailureCode.AUTH_REQUIRED
            ):
                self._sessions.mark_reauth_required(session)
                reauth_flagged = True

        if session is not None:
            try:
                self._sessions.save_refreshed(session, self._browser.get_cookies())
            except Exception as exc:
                logger.warning("Could not save refreshed cookies: %s", exc)

        return results

    def run_check(
        self, booking: Booking, session_mode: SessionMode = SessionMode.AUTHENTICATED
    ) -> CheckResult:
        """Check one booking via the search journey. Always returns; never raises."""
        recorder = TraceRecorder(booking.booking_id)
        escalator: BrowserAgent | None = None
        try:
            result = self._run_check_inner(booking, recorder, session_mode)
        except Exception as exc:  # belt and braces: the never-raise contract
            logger.exception("Unexpected error checking booking %s", booking.booking_id)
            result = CheckResult.failure(
                booking.booking_id,
                datetime.now(UTC),
                FailureReason(code=FailureCode.UNKNOWN, detail=str(exc)),
            )
        else:
            escalator = self._last_escalator
        self._persist_trace(recorder, result, escalator)
        return result

    def _run_check_inner(
        self, booking: Booking, recorder: TraceRecorder, session_mode: SessionMode
    ) -> CheckResult:
        now = datetime.now(UTC)
        self._last_escalator = None

        if self._llm_factory is not None:
            try:
                self._llm = self._llm_factory.for_booking(booking)
                self._brain = self._llm_factory.agent_brain_for_booking(booking)
            except UserKeyInvalidError as exc:
                return CheckResult.failure(
                    booking.booking_id,
                    now,
                    FailureReason(code=FailureCode.USER_KEY_INVALID, detail=str(exc)),
                )

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

        budget = AgentBudget(self._agent_settings, clock=self._clock)
        escalator: BrowserAgent | None = None
        if self._brain is not None:
            escalator = BrowserAgent(self._browser, self._brain, budget, recorder)
            self._last_escalator = escalator

        journey = SearchJourney(
            self._browser,
            escalator=escalator,
            recorder=recorder,
            checkpoint=budget.check_time,
            session_mode=session_mode,
        ).run(booking)

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
            try:
                llm_candidates = self._try_llm_offers(page_text, booking, budget)
            except BudgetExceeded as exc:
                return CheckResult.failure(
                    booking.booking_id,
                    now,
                    FailureReason(code=FailureCode.BUDGET_EXCEEDED, detail=str(exc)),
                )
            if llm_candidates is not None:
                candidates = llm_candidates
                method = ExtractionMethod.LLM

        if journey.agent_assisted:
            method = ExtractionMethod.AGENT  # US-020: scripted vs agent-assisted marker

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

        if session_mode is SessionMode.LOGGED_OUT:
            # US-035: no natural CheckResult field for this (schema owned
            # elsewhere) — annotate via logging so operators can see that a
            # price is a public rate and may miss member/Genius discounts.
            logger.info(
                "Check for booking %s used a public (logged-out) rate.",
                booking.booking_id,
            )
        return self._to_success(booking, selection.chosen, method, now)

    def _persist_trace(
        self,
        recorder: TraceRecorder,
        result: CheckResult,
        escalator: BrowserAgent | None,
    ) -> None:
        if self._trace_repo is not None:
            try:
                self._trace_repo.add(recorder.finish(result))
            except Exception as exc:
                logger.warning("Could not persist check trace: %s", exc)
        if self._snapshots is not None and result.failure_reason is not None:
            page_text = ""
            try:
                page_text = self._browser.snapshot().text
            except Exception:
                pass
            screenshot = escalator.last_screenshot if escalator else None
            self._snapshots.write_failure(result.check_id, page_text, screenshot)

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
        self, page_text: str, booking: Booking, budget: AgentBudget
    ) -> list[OfferCandidate] | None:
        if self._llm is None:
            logger.info("LLM extractor not configured; DOM-only offer parsing")
            return None
        budget.consume_llm_call()  # extraction draws from the same pool (ADR-017)
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
