from __future__ import annotations

from decimal import Decimal

from booksaver.application.ports import ExtractionResult
from booksaver.domain.check_result import CheckOutcome, ExtractionMethod, FailureCode
from booksaver.domain.session import SessionStatus
from booksaver.domain.value_objects import Money
from booksaver.monitor.check_job import BookingComMonitor, booking_url
from booksaver.monitor.failure_tracker import FailureTracker
from booksaver.monitor.session_manager import SessionManager

from .fakes import (
    FakeBookingRepository,
    FakeBrowserSession,
    FakeCheckHistoryRepository,
    FakeLLMExtractor,
    FakeSessionRepository,
    make_booking,
    make_session,
)

_PAGE_WITH_PRICE = """\
Your reservation at Hotel Test
Standard Double Room
Free cancellation until 1 September
Total price: € 380.00
"""

_PAGE_WITHOUT_PRICE = """\
Your reservation at Hotel Test
Standard Double Room
Contact the property for pricing details.
"""


def _make_monitor(
    browser: FakeBrowserSession,
    llm: FakeLLMExtractor | None = None,
    bookings: list | None = None,
    session_repo: FakeSessionRepository | None = None,
) -> tuple[BookingComMonitor, FakeCheckHistoryRepository, FakeSessionRepository]:
    history = FakeCheckHistoryRepository()
    session_repo = session_repo or FakeSessionRepository(make_session())
    monitor = BookingComMonitor(
        browser=browser,
        session_manager=SessionManager(session_repo),
        check_history=history,
        booking_repo=FakeBookingRepository(bookings if bookings is not None else [make_booking()]),
        failure_tracker=FailureTracker(history),
        llm=llm,
    )
    return monitor, history, session_repo


# ── booking_url ───────────────────────────────────────────────────────────────

def test_booking_url_uses_ref_when_it_is_a_url() -> None:
    booking = make_booking(ref="https://www.booking.com/hotel/nl/test.html")
    assert booking_url(booking) == "https://www.booking.com/hotel/nl/test.html"


def test_booking_url_falls_back_to_manage_page_for_non_url_ref() -> None:
    booking = make_booking(ref="hotel-test-123")
    assert booking_url(booking) == "https://secure.booking.com/myreservations.html"


# ── run_check: DOM path ───────────────────────────────────────────────────────

def test_successful_dom_extraction() -> None:
    browser = FakeBrowserSession(page_text=_PAGE_WITH_PRICE)
    monitor, _, _ = _make_monitor(browser)

    result = monitor.run_check(make_booking())

    assert result.outcome is CheckOutcome.SUCCESS
    assert result.extraction_method is ExtractionMethod.DOM
    assert result.live_price == Money(amount=Decimal("380.00"), currency="EUR")
    assert result.refund_indicators is not None
    assert result.refund_indicators.is_refundable is True


def test_navigation_failure_returns_failure_result() -> None:
    browser = FakeBrowserSession(fail_navigation=True)
    monitor, _, _ = _make_monitor(browser)

    result = monitor.run_check(make_booking())

    assert result.outcome is CheckOutcome.FAILURE
    assert result.failure_reason is not None
    assert result.failure_reason.code is FailureCode.NAVIGATION_ERROR


def test_unauthenticated_page_returns_auth_required() -> None:
    browser = FakeBrowserSession(page_text=_PAGE_WITH_PRICE, authenticated=False)
    monitor, _, _ = _make_monitor(browser)

    result = monitor.run_check(make_booking())

    assert result.outcome is CheckOutcome.FAILURE
    assert result.failure_reason is not None
    assert result.failure_reason.code is FailureCode.AUTH_REQUIRED


# ── run_check: LLM fallback ───────────────────────────────────────────────────

def test_llm_fallback_when_dom_finds_no_price() -> None:
    browser = FakeBrowserSession(page_text=_PAGE_WITHOUT_PRICE)
    llm = FakeLLMExtractor(
        result=ExtractionResult(
            price=Money(amount=Decimal("350.00"), currency="EUR"),
            is_refundable=True,
            cancellation_deadline_raw="until 1 September",
            confidence=0.9,
        )
    )
    monitor, _, _ = _make_monitor(browser, llm=llm)

    result = monitor.run_check(make_booking())

    assert result.outcome is CheckOutcome.SUCCESS
    assert result.extraction_method is ExtractionMethod.LLM
    assert result.live_price == Money(amount=Decimal("350.00"), currency="EUR")
    assert len(llm.calls) == 1


def test_llm_not_called_when_dom_succeeds() -> None:
    browser = FakeBrowserSession(page_text=_PAGE_WITH_PRICE)
    llm = FakeLLMExtractor()
    monitor, _, _ = _make_monitor(browser, llm=llm)

    result = monitor.run_check(make_booking())

    assert result.outcome is CheckOutcome.SUCCESS
    assert llm.calls == []


def test_extraction_failed_when_both_dom_and_llm_miss() -> None:
    browser = FakeBrowserSession(page_text=_PAGE_WITHOUT_PRICE)
    llm = FakeLLMExtractor()  # zero-confidence default
    monitor, _, _ = _make_monitor(browser, llm=llm)

    result = monitor.run_check(make_booking())

    assert result.outcome is CheckOutcome.FAILURE
    assert result.failure_reason is not None
    assert result.failure_reason.code is FailureCode.EXTRACTION_FAILED


def test_llm_exception_degrades_to_extraction_failed() -> None:
    browser = FakeBrowserSession(page_text=_PAGE_WITHOUT_PRICE)
    llm = FakeLLMExtractor(raise_error=True)
    monitor, _, _ = _make_monitor(browser, llm=llm)

    result = monitor.run_check(make_booking())

    assert result.outcome is CheckOutcome.FAILURE  # never raises


def test_no_llm_configured_is_dom_only() -> None:
    browser = FakeBrowserSession(page_text=_PAGE_WITHOUT_PRICE)
    monitor, _, _ = _make_monitor(browser, llm=None)

    result = monitor.run_check(make_booking())

    assert result.outcome is CheckOutcome.FAILURE


# ── run_all_active ────────────────────────────────────────────────────────────

def test_run_all_active_records_history_for_each_booking() -> None:
    bookings = [make_booking("b-1"), make_booking("b-2")]
    browser = FakeBrowserSession(page_text=_PAGE_WITH_PRICE)
    monitor, history, _ = _make_monitor(browser, bookings=bookings)

    results = monitor.run_all_active()

    assert len(results) == 2
    assert len(history.results) == 2
    assert {r.booking_id for r in history.results} == {"b-1", "b-2"}


def test_run_all_active_without_session_records_auth_failures() -> None:
    browser = FakeBrowserSession(page_text=_PAGE_WITH_PRICE)
    session_repo = FakeSessionRepository(session=None)  # no session saved
    monitor, history, _ = _make_monitor(browser, session_repo=session_repo)

    results = monitor.run_all_active()

    assert len(results) == 1
    assert results[0].outcome is CheckOutcome.FAILURE
    assert results[0].failure_reason is not None
    assert results[0].failure_reason.code is FailureCode.AUTH_REQUIRED
    assert browser.opened_urls == []  # never even navigated


def test_run_all_active_saves_refreshed_cookies() -> None:
    browser = FakeBrowserSession(page_text=_PAGE_WITH_PRICE)
    monitor, _, session_repo = _make_monitor(browser)

    monitor.run_all_active()

    assert session_repo.saved  # refreshed cookies were persisted
    assert session_repo.saved[-1].cookies == b'[{"name": "fresh"}]'


def test_run_all_active_flags_reauth_on_auth_failure() -> None:
    browser = FakeBrowserSession(page_text=_PAGE_WITH_PRICE, authenticated=False)
    monitor, _, session_repo = _make_monitor(browser)

    monitor.run_all_active()

    statuses = [s.status for s in session_repo.saved]
    assert SessionStatus.REQUIRES_REAUTH in statuses


def test_run_all_active_with_no_bookings_is_a_noop() -> None:
    browser = FakeBrowserSession(page_text=_PAGE_WITH_PRICE)
    monitor, history, _ = _make_monitor(browser, bookings=[])

    results = monitor.run_all_active()

    assert results == []
    assert history.results == []
    assert browser.opened_urls == []
