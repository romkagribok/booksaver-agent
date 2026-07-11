from __future__ import annotations

from decimal import Decimal

from booksaver.domain.check_result import CheckOutcome, ExtractionMethod, FailureCode
from booksaver.domain.offer import OfferCandidate
from booksaver.domain.savings import SavingsOpportunity, detect_savings
from booksaver.domain.value_objects import Money
from booksaver.monitor.failure_tracker import FailureTracker
from booksaver.monitor.search_check_job import BookingComSearchMonitor
from booksaver.monitor.session_manager import SessionManager

from .fakes import (
    FakeBookingRepository,
    FakeCheckHistoryRepository,
    FakeInteractiveBrowser,
    FakeLLMExtractor,
    FakeSessionRepository,
    make_booking,
    make_session,
)

_PROPERTY_URL = (
    "https://www.booking.com/hotel/test.html"
    "?checkin=2026-09-01&checkout=2026-09-05&group_adults=2"
)

_ROOM_TABLE = """\
Standard Double
€ 350.00
Free cancellation before 30 August 2026
Deluxe Suite
€ 520.00
Non-refundable
"""


def _happy_browser() -> FakeInteractiveBrowser:
    browser = FakeInteractiveBrowser(titles=["Hotel Test"], page_text=_ROOM_TABLE)
    browser.property_url = _PROPERTY_URL
    return browser


def _monitor(
    browser: FakeInteractiveBrowser,
    bookings: list | None = None,
    llm: FakeLLMExtractor | None = None,
    session: FakeSessionRepository | None = None,
) -> tuple[BookingComSearchMonitor, FakeCheckHistoryRepository]:
    history = FakeCheckHistoryRepository()
    monitor = BookingComSearchMonitor(
        browser=browser,
        session_manager=SessionManager(session or FakeSessionRepository(make_session())),
        check_history=history,
        booking_repo=FakeBookingRepository(bookings if bookings is not None else []),
        failure_tracker=FailureTracker(history),
        llm=llm,
    )
    return monitor, history


class TestOccupancyGuard:
    def test_missing_occupancy_fails_without_browser(self):
        browser = _happy_browser()
        monitor, _ = _monitor(browser)
        result = monitor.run_check(make_booking(occupancy=None))
        assert result.outcome is CheckOutcome.FAILURE
        assert result.failure_reason.code is FailureCode.OCCUPANCY_MISSING
        assert "set-occupancy" in result.failure_reason.detail
        assert browser.actions == []  # no navigation happened


class TestScriptedHappyPath:
    def test_dom_exact_match_success_without_llm(self):
        monitor, _ = _monitor(_happy_browser())
        result = monitor.run_check(make_booking())
        assert result.outcome is CheckOutcome.SUCCESS
        assert result.extraction_method is ExtractionMethod.DOM
        assert result.live_price == Money(amount=Decimal("350.00"), currency="EUR")
        assert result.refund_indicators.is_refundable is True

    def test_success_feeds_existing_savings_detection(self):
        booking = make_booking()  # baseline 400.00 EUR
        monitor, _ = _monitor(_happy_browser())
        result = monitor.run_check(booking)
        detection = detect_savings(booking, result)
        assert isinstance(detection, SavingsOpportunity)
        assert detection.amount_saved.amount == Decimal("50.00")

    def test_extracted_fields_carry_verified_booking_context(self):
        booking = make_booking()
        monitor, _ = _monitor(_happy_browser())
        result = monitor.run_check(booking)
        fields = result.extracted_fields
        assert fields.property_name == booking.property.name
        assert fields.check_in == booking.stay_dates.check_in
        assert fields.check_out == booking.stay_dates.check_out
        assert fields.room_label == "Standard Double"  # exact match is echoed


class TestLLMFallback:
    def test_drift_match_uses_llm_and_omits_room_label(self):
        browser = _happy_browser()
        browser.page_text = "Cosy Double Room\n€ 340.00\nFree cancellation until check-in"
        drift_offer = OfferCandidate(
            room_label="Cosy Double Room",
            total=Money(amount=Decimal("340.00"), currency="EUR"),
            is_refundable=True,
            cancellation_text="Free cancellation until check-in",
            matches_room=True,
            match_confidence=0.8,
        )
        llm = FakeLLMExtractor(offers=[drift_offer])
        booking = make_booking()
        monitor, _ = _monitor(browser, llm=llm)
        result = monitor.run_check(booking)
        assert result.outcome is CheckOutcome.SUCCESS
        assert result.extraction_method is ExtractionMethod.LLM
        assert len(llm.offer_calls) == 1
        # Drift-matched label must not contradict the booking downstream
        assert result.extracted_fields.room_label is None
        detection = detect_savings(booking, result)
        assert isinstance(detection, SavingsOpportunity)

    def test_no_candidates_at_all_is_extraction_failed(self):
        browser = _happy_browser()
        browser.page_text = "Nothing that looks like a rate table"
        monitor, _ = _monitor(browser, llm=FakeLLMExtractor(offers=[]))
        result = monitor.run_check(make_booking())
        assert result.failure_reason.code is FailureCode.EXTRACTION_FAILED

    def test_candidates_but_none_equivalent_is_no_equivalent_offer(self):
        browser = _happy_browser()
        browser.page_text = "Deluxe Suite\n€ 520.00\nNon-refundable"
        monitor, _ = _monitor(browser)
        result = monitor.run_check(make_booking())
        assert result.failure_reason.code is FailureCode.NO_EQUIVALENT_OFFER
        assert "not_refundable" in result.failure_reason.detail

    def test_llm_error_degrades_to_dom_candidates(self):
        browser = _happy_browser()
        browser.page_text = "Deluxe Suite\n€ 520.00\nNon-refundable"
        monitor, _ = _monitor(browser, llm=FakeLLMExtractor(raise_error=True))
        result = monitor.run_check(make_booking())
        # DOM found a candidate; it just isn't equivalent
        assert result.failure_reason.code is FailureCode.NO_EQUIVALENT_OFFER


class TestJourneyFailureMapping:
    def test_failed_step_lands_in_failure_detail(self):
        browser = _happy_browser()
        browser.titles = ["Wrong Hotel"]
        monitor, _ = _monitor(browser)
        result = monitor.run_check(make_booking())
        assert result.failure_reason.code is FailureCode.PROPERTY_NOT_FOUND
        assert "step=locate_property" in result.failure_reason.detail


class TestRunAllActive:
    def test_no_session_runs_logged_out_instead_of_failing(self):
        bookings = [make_booking("b-1"), make_booking("b-2")]
        browser = _happy_browser()
        monitor, history = _monitor(
            browser, bookings=bookings, session=FakeSessionRepository(None)
        )
        results = monitor.run_all_active()
        assert len(results) == 2
        assert all(r.outcome is CheckOutcome.SUCCESS for r in results)
        assert len(history.results) == 2
        # No session existed, so nothing was restored and nothing was saved.
        assert browser.restored_cookies == []

    def test_checks_recorded_and_cookies_refreshed(self):
        session_repo = FakeSessionRepository(make_session())
        bookings = [make_booking("b-1")]
        monitor, history = _monitor(
            _happy_browser(), bookings=bookings, session=session_repo
        )
        results = monitor.run_all_active()
        assert len(results) == 1
        assert results[0].outcome is CheckOutcome.SUCCESS
        assert history.results[0].check_id == results[0].check_id
        assert session_repo.saved  # refreshed cookies persisted

    def test_mixed_bookings_one_missing_occupancy(self):
        bookings = [make_booking("b-1", occupancy=None), make_booking("b-2")]
        monitor, _ = _monitor(_happy_browser(), bookings=bookings)
        results = monitor.run_all_active()
        codes = {
            r.booking_id: r.failure_reason.code if r.failure_reason else None
            for r in results
        }
        assert codes["b-1"] is FailureCode.OCCUPANCY_MISSING
        assert codes["b-2"] is None  # succeeded


class _FakeLLMClientFactory:
    """Fakes the US-027 hybrid-billing seam: raises on `for_booking` to
    simulate a booking owner's invalid/undecryptable personal key."""

    def __init__(self, raise_error: bool = True) -> None:
        self._raise_error = raise_error
        self.calls: list[str] = []

    def for_booking(self, booking):
        self.calls.append(booking.booking_id if booking else "none")
        if self._raise_error:
            from booksaver.domain.errors import UserKeyInvalidError

            raise UserKeyInvalidError(user_id=7, detail="stub")
        return None

    def agent_brain_for_booking(self, booking):
        return None


class TestHybridBillingIntegration:
    """US-027: a per-booking LLMClientFactory that raises UserKeyInvalidError
    fails only that booking's check with FailureCode.USER_KEY_INVALID —
    every other constructor-injected-llm test above is unaffected because
    `llm_factory` defaults to None."""

    def test_invalid_user_key_fails_the_check_with_user_key_invalid(self):
        history = FakeCheckHistoryRepository()
        factory = _FakeLLMClientFactory(raise_error=True)
        monitor = BookingComSearchMonitor(
            browser=_happy_browser(),
            session_manager=SessionManager(FakeSessionRepository(make_session())),
            check_history=history,
            booking_repo=FakeBookingRepository([]),
            failure_tracker=FailureTracker(history),
            llm_factory=factory,
        )
        result = monitor.run_check(make_booking())
        assert result.outcome is CheckOutcome.FAILURE
        assert result.failure_reason.code is FailureCode.USER_KEY_INVALID
        assert factory.calls == ["b-1"]

    def test_no_user_key_error_uses_the_factory_resolved_clients(self):
        history = FakeCheckHistoryRepository()
        factory = _FakeLLMClientFactory(raise_error=False)
        monitor = BookingComSearchMonitor(
            browser=_happy_browser(),
            session_manager=SessionManager(FakeSessionRepository(make_session())),
            check_history=history,
            booking_repo=FakeBookingRepository([]),
            failure_tracker=FailureTracker(history),
            llm_factory=factory,
        )
        result = monitor.run_check(make_booking())
        assert result.outcome is CheckOutcome.SUCCESS
        assert factory.calls == ["b-1"]
