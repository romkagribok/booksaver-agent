from __future__ import annotations

import re
from datetime import UTC, date, datetime
from decimal import Decimal

from booksaver.application.ports import ExtractionResult, PageContent, PageSnapshot
from booksaver.domain.agent import (
    AgentAction,
    AgentActionType,
    ElementInfo,
    Observation,
)
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
        calendar_month: date | None = date(2026, 9, 1),
        search_box_value: str = "",
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
        self.elements: tuple[ElementInfo, ...] = ()  # agent observation elements
        self.fail_refs: set[str] = set()  # refs whose act() raises
        self.on_act = None  # optional hook: (browser, action) -> None
        self.actions: list[tuple[str, str]] = []
        self.restored_cookies: list[bytes] = []
        # When set, [data-date] cells exist only for this month and the next.
        self.calendar_month = calendar_month
        self.search_box_value = search_box_value

    def _month_index(self, d: date) -> int:
        return d.year * 12 + (d.month - 1)

    def _calendar_date_visible(self, iso_date: str) -> bool:
        if "data-date" in self.fail_selectors:
            return False
        if self.calendar_month is None:
            return True
        try:
            cell = date.fromisoformat(iso_date)
        except ValueError:
            return False
        anchor = self._month_index(self.calendar_month)
        cell_idx = self._month_index(cell)
        return anchor <= cell_idx <= anchor + 1

    def _shift_calendar(self, direction: str) -> None:
        if self.calendar_month is None:
            return
        month = self.calendar_month.month + (1 if direction == "next" else -1)
        year = self.calendar_month.year
        if month < 1:
            month, year = 12, year - 1
        elif month > 12:
            month, year = 1, year + 1
        self.calendar_month = date(year, month, 1)
        name = self.calendar_month.strftime("%B %Y")
        next_month = date(year + (1 if month == 12 else 0), (month % 12) + 1, 1)
        self.page_text = f"{name}\n{next_month.strftime('%B %Y')}\n{self.page_text}"

    def _check(self, selector: str) -> None:
        for fragment in self.fail_selectors:
            if fragment in selector:
                raise RuntimeError(f"selector not found: {selector}")

    def goto(self, url: str) -> None:
        self.actions.append(("goto", url))
        if self.fail_goto:
            raise TimeoutError(f"Navigation to {url} timed out")
        self.url = url
        if "/hotel/" in url or "checkin=" in url:
            self.present_selectors.update({"#hprt-table", '[data-testid="rt-room-table"]'})

    def click(self, selector: str) -> None:
        self.actions.append(("click", selector))
        if "Previous month" in selector or "calendar-prev" in selector:
            self._shift_calendar("prev")
        elif "Next month" in selector or "calendar-next" in selector:
            self._shift_calendar("next")
        self._check(selector)
        if "title" in selector and self.property_url:
            self.url = self.property_url

    def click_first_visible(self, selector: str) -> None:
        self.click(selector)

    def fill(self, selector: str, text: str) -> None:
        self.actions.append(("fill", f"{selector}={text}"))
        if 'name="ss"' in selector:
            self.search_box_value = text
        self._check(selector)

    def press(self, selector: str, key: str) -> None:
        self.actions.append(("press", f"{selector}:{key}"))
        self._check(selector)

    def wait_for(self, selector: str, timeout_ms: int | None = None) -> None:
        self.actions.append(("wait_for", selector))
        self._check(selector)

    def exists(self, selector: str) -> bool:
        if selector in self.present_selectors:
            return True
        match = re.search(r'\[data-date="(\d{4}-\d{2}-\d{2})"\]', selector)
        if match is not None:
            return self._calendar_date_visible(match.group(1))
        if "Previous month" in selector or "calendar-prev" in selector:
            return "calendar-prev" not in self.fail_selectors
        if "Next month" in selector or "calendar-next" in selector:
            return "calendar-next" not in self.fail_selectors
        return False

    def query_text(self, selector: str) -> list[str]:
        self._check(selector)
        if "title" in selector:
            return list(self.titles)
        if selector.startswith("input#"):
            name = selector.removeprefix("input#")
            if name in self.counters:
                return [str(self.counters[name])]
        if 'name="ss"' in selector and self.search_box_value:
            return [self.search_box_value]
        return []

    def query_attr(self, selector: str, attr: str) -> list[str]:
        self._check(selector)
        if attr == "href" and "title-link" in selector:
            if self.property_url:
                return [self.property_url for _ in self.titles] or [self.property_url]
            return []
        if attr == "data-date" and "data-date" in selector:
            if self.calendar_month is None:
                return []
            # Two visible months of day cells, matching Booking.com's dual calendar.
            values: list[str] = []
            for offset in (0, 1):
                month = self.calendar_month.month + offset
                year = self.calendar_month.year
                if month > 12:
                    month, year = month - 12, year + 1
                # First of month through a few days is enough for month detection.
                for day in range(1, 8):
                    try:
                        values.append(date(year, month, day).isoformat())
                    except ValueError:
                        break
            return values
        return []

    def snapshot(self) -> PageSnapshot:
        return PageSnapshot(url=self.url, title="", text=self.page_text)

    # ── agent surface (bolt 007) ────────────────────────────────────────────

    def observe(self) -> Observation:
        return Observation(
            url=self.url,
            title="",
            text=self.page_text,
            elements=tuple(getattr(self, "elements", ())),
        )

    def act(self, action: AgentAction) -> None:
        self.actions.append(("act", f"{action.type.value} ref={action.ref}"))
        fail_refs = getattr(self, "fail_refs", set())
        if action.ref in fail_refs:
            raise RuntimeError(f"element {action.ref} not interactable")
        if action.type is AgentActionType.SCROLL:
            return
        on_act = getattr(self, "on_act", None)
        if on_act is not None:
            on_act(self, action)

    def screenshot(self) -> bytes:
        self.actions.append(("screenshot", ""))
        return b"\x89PNG-fake"

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


class FakeAgentBrain:
    """Scripted AgentBrain: returns queued actions in order; gives up when the
    script runs dry."""

    def __init__(self, script: list[AgentAction]) -> None:
        self.script = list(script)
        self.decisions: list[Observation] = []

    def decide(
        self, goal: str, observation: Observation, history: list[str]
    ) -> AgentAction:
        self.decisions.append(observation)
        if self.script:
            return self.script.pop(0)
        return AgentAction(type=AgentActionType.GIVE_UP, value="script exhausted")
