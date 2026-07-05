from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

from booksaver.application.ports import ExtractionResult, PageContent, PageSnapshot
from booksaver.domain.check_result import CheckResult
from booksaver.domain.models import Booking
from booksaver.domain.offer import OfferCandidate
from booksaver.domain.session import SessionState
from booksaver.domain.value_objects import (
    ConfirmationId,
    Money,
    Occupancy,
    Platform,
    ProductType,
    Property,
    RefundabilityPolicy,
    RoomType,
    StayDates,
)


def make_booking(
    booking_id: str = "b-1",
    ref: str = "https://example.com/hotel",
    occupancy: Occupancy | None = Occupancy(adults=2),
) -> Booking:
    return Booking(
        booking_id=booking_id,
        platform=Platform.BOOKING_COM,
        product_type=ProductType.HOTEL,
        confirmation_id=ConfirmationId(f"CONF-{booking_id}"),
        property=Property(name="Hotel Test", booking_com_ref=ref),
        stay_dates=StayDates(check_in=date(2026, 9, 1), check_out=date(2026, 9, 5)),
        room_type=RoomType(label="Standard Double"),
        baseline_price=Money(amount=Decimal("400.00"), currency="EUR"),
        refundability=RefundabilityPolicy(is_refundable=True, note="Free cancellation"),
        registered_at=datetime.now(UTC),
        occupancy=occupancy,
    )


class FakeBookingRepository:
    def __init__(self, bookings: list[Booking] | None = None) -> None:
        self.bookings = bookings or []

    def add(self, booking: Booking) -> None:
        self.bookings.append(booking)

    def get_by_id(self, booking_id: str) -> Booking | None:
        return next((b for b in self.bookings if b.booking_id == booking_id), None)

    def get_by_confirmation(self, confirmation_id: ConfirmationId) -> Booking | None:
        return next(
            (b for b in self.bookings if b.confirmation_id == confirmation_id), None
        )

    def list_active(self) -> list[Booking]:
        return [b for b in self.bookings if b.status.value == "active"]

    def exists(self, confirmation_id: ConfirmationId) -> bool:
        return self.get_by_confirmation(confirmation_id) is not None


class FakeCheckHistoryRepository:
    def __init__(self) -> None:
        self.results: list[CheckResult] = []

    def add(self, result: CheckResult) -> None:
        self.results.append(result)

    def get_recent(self, booking_id: str, limit: int = 10) -> list[CheckResult]:
        matching = [r for r in self.results if r.booking_id == booking_id]
        return list(reversed(matching))[:limit]

    def count_consecutive_failures(self, booking_id: str) -> int:
        matching = [r for r in self.results if r.booking_id == booking_id]
        count = 0
        for result in reversed(matching):
            if result.outcome.value != "failure":
                break
            count += 1
        return count


class FakeSessionRepository:
    def __init__(self, session: SessionState | None = None) -> None:
        self.session = session
        self.saved: list[SessionState] = []

    def load(self, platform: Platform) -> SessionState | None:
        return self.session

    def save(self, session: SessionState) -> None:
        self.session = session
        self.saved.append(session)


class FakeBrowserSession:
    def __init__(
        self,
        page_text: str = "",
        authenticated: bool = True,
        fail_navigation: bool = False,
    ) -> None:
        self.page_text = page_text
        self.authenticated = authenticated
        self.fail_navigation = fail_navigation
        self.opened_urls: list[str] = []
        self.restored_cookies: list[bytes] = []

    def open_page(self, url: str) -> PageContent:
        self.opened_urls.append(url)
        if self.fail_navigation:
            raise TimeoutError(f"Navigation to {url} timed out")
        return PageContent(url=url, html=f"<body>{self.page_text}</body>", text=self.page_text)

    def get_cookies(self) -> bytes:
        return b'[{"name": "fresh"}]'

    def restore_cookies(self, data: bytes) -> None:
        self.restored_cookies.append(data)

    def is_authenticated(self) -> bool:
        return self.authenticated


class FakeLLMExtractor:
    def __init__(
        self,
        result: ExtractionResult | None = None,
        raise_error: bool = False,
        offers: list[OfferCandidate] | None = None,
    ) -> None:
        self.result = result or ExtractionResult(
            price=None, is_refundable=None, cancellation_deadline_raw=None, confidence=0.0
        )
        self.raise_error = raise_error
        self.offers = offers or []
        self.calls: list[str] = []
        self.offer_calls: list[str] = []

    def extract_price(self, page_text: str, booking: Booking) -> ExtractionResult:
        self.calls.append(page_text)
        if self.raise_error:
            raise RuntimeError("LLM API unavailable")
        return self.result

    def extract_offers(self, page_text: str, booking: Booking) -> list[OfferCandidate]:
        self.offer_calls.append(page_text)
        if self.raise_error:
            raise RuntimeError("LLM API unavailable")
        return self.offers


class FakeInteractiveBrowser:
    """Scriptable InteractiveBrowser: selectors in fail_selectors raise; property
    titles, occupancy counters, page text, and URL are set per test."""

    def __init__(
        self,
        titles: list[str] | None = None,
        page_text: str = "",
        url: str = "https://www.booking.com",
        counters: dict[str, int] | None = None,
        fail_selectors: frozenset[str] | set[str] = frozenset(),
        fail_goto: bool = False,
        authenticated: bool = True,
        present_selectors: set[str] | None = None,
    ) -> None:
        self.titles = titles or []
        self.page_text = page_text
        self.url = url
        self.counters = counters or {"group_adults": 2, "group_children": 0, "no_rooms": 1}
        self.fail_selectors = set(fail_selectors)
        self.fail_goto = fail_goto
        self.authenticated = authenticated
        self.present_selectors = present_selectors or set()
        self.property_url: str | None = None  # url after clicking a result title
        self.actions: list[tuple[str, str]] = []
        self.restored_cookies: list[bytes] = []

    def _check(self, selector: str) -> None:
        for fragment in self.fail_selectors:
            if fragment in selector:
                raise RuntimeError(f"selector not found: {selector}")

    def goto(self, url: str) -> None:
        self.actions.append(("goto", url))
        if self.fail_goto:
            raise TimeoutError(f"Navigation to {url} timed out")
        self.url = url

    def click(self, selector: str) -> None:
        self.actions.append(("click", selector))
        self._check(selector)
        if "title" in selector and self.property_url:
            self.url = self.property_url

    def fill(self, selector: str, text: str) -> None:
        self.actions.append(("fill", f"{selector}={text}"))
        self._check(selector)

    def press(self, selector: str, key: str) -> None:
        self.actions.append(("press", f"{selector}:{key}"))
        self._check(selector)

    def wait_for(self, selector: str, timeout_ms: int | None = None) -> None:
        self.actions.append(("wait_for", selector))
        self._check(selector)

    def exists(self, selector: str) -> bool:
        return selector in self.present_selectors

    def query_text(self, selector: str) -> list[str]:
        self._check(selector)
        if "title" in selector:
            return list(self.titles)
        if selector.startswith("input#"):
            name = selector.removeprefix("input#")
            if name in self.counters:
                return [str(self.counters[name])]
        return []

    def snapshot(self) -> PageSnapshot:
        return PageSnapshot(url=self.url, title="", text=self.page_text)

    def get_cookies(self) -> bytes:
        return b'[{"name": "fresh"}]'

    def restore_cookies(self, data: bytes) -> None:
        self.restored_cookies.append(data)

    def is_authenticated(self) -> bool:
        return self.authenticated


def make_session(cookies: bytes = b"[]") -> SessionState:
    return SessionState.new(
        platform=Platform.BOOKING_COM,
        cookies=cookies,
        authenticated_at=datetime.now(UTC),
    )
