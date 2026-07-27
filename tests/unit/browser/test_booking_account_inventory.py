from booksaver.application.ports import PageContent
from booksaver.domain.account_sync import (
    InventoryCompleteness,
    ReservationLifecycle,
    SynchronizationFailureCode,
)
from booksaver.infrastructure.browser.booking_account_inventory import (
    BookingComAccountInventorySource,
)
from booksaver.infrastructure.browser.playwright_adapter import (
    PlaywrightInteractiveBrowser,
)


class _Browser:
    def __init__(self, pages: list[PageContent], *, authenticated: bool = True) -> None:
        self.pages = pages
        self.authenticated = authenticated

    def open_page(self, _url: str) -> PageContent:
        return self.pages.pop(0)

    def is_authenticated(self) -> bool:
        return self.authenticated


def test_discovers_eligible_and_incomplete_cards_across_pages() -> None:
    first = PageContent(
        "https://secure.booking.com/myreservations.html",
        """
        <main data-testid="bookings-list"
              data-inventory-scopes="upcoming,past,cancelled">
          <article data-testid="reservation-card"
            data-reservation-id="remote-1" data-confirmation-id="CONF-1"
            data-status="confirmed" data-property-name="Hotel One"
            data-property-url="hotel-one" data-checkin="2027-01-10"
            data-checkout="2027-01-12" data-room-type="King room"
            data-total-amount="200" data-currency="USD"
            data-refundable="true" data-adults="2"></article>
          <a rel="next" href="/myreservations.html?page=2">Next</a>
        </main>
        """,
        "",
    )
    second = PageContent(
        "https://secure.booking.com/myreservations.html?page=2",
        """
        <main data-testid="bookings-list">
          <article data-testid="reservation-card"
            data-reservation-id="remote-2" data-status="cancelled"
            data-property-name="Hotel Two"></article>
        </main>
        """,
        "",
    )

    result = BookingComAccountInventorySource().discover(_Browser([first, second]))

    assert result.completeness is InventoryCompleteness.COMPLETE
    assert [item.remote_id for item in result.observations] == ["remote-1", "remote-2"]
    assert result.observations[0].lifecycle is ReservationLifecycle.UPCOMING
    assert result.observations[0].occupancy is not None
    assert result.observations[1].lifecycle is ReservationLifecycle.CANCELLED


def test_traverses_supported_past_and_cancelled_inventory_tabs() -> None:
    first = PageContent(
        "https://secure.booking.com/myreservations.html",
        """
        <main data-testid="bookings-empty-state">No upcoming stays</main>
        <a data-testid="past-bookings-tab"
           href="/myreservations.html?scope=past">Past</a>
        <a data-testid="cancelled-bookings-tab"
           href="/myreservations.html?scope=cancelled">Cancelled</a>
        """,
        "",
    )
    past = PageContent(
        "https://secure.booking.com/myreservations.html?scope=cancelled",
        """
        <main data-testid="bookings-list">
          <article data-testid="reservation-card"
            data-reservation-id="cancelled-1" data-status="cancelled"
            data-property-name="Cancelled Hotel"></article>
        </main>
        """,
        "",
    )
    cancelled = PageContent(
        "https://secure.booking.com/myreservations.html?scope=past",
        """
        <main data-testid="bookings-list">
          <article data-testid="reservation-card"
            data-reservation-id="past-1" data-status="completed"
            data-property-name="Past Hotel"></article>
        </main>
        """,
        "",
    )

    result = BookingComAccountInventorySource().discover(
        _Browser([first, past, cancelled])
    )

    assert result.completeness is InventoryCompleteness.COMPLETE
    assert {item.lifecycle for item in result.observations} == {
        ReservationLifecycle.CANCELLED,
        ReservationLifecycle.COMPLETED,
    }


def test_scope_links_are_discovered_from_control_text_not_testid() -> None:
    upcoming = PageContent(
        "https://secure.booking.com/myreservations.html",
        """
        <main data-testid="bookings-empty-state">No upcoming stays</main>
        <a role="tab" href="/myreservations.html?scope=past"><span>Past</span></a>
        <a role="tab" href="/myreservations.html?scope=cancelled">Cancelled</a>
        """,
        "",
    )
    past = PageContent(
        "https://secure.booking.com/myreservations.html?scope=cancelled",
        "<main data-testid='bookings-empty-state'>No cancelled stays</main>",
        "",
    )
    cancelled = PageContent(
        "https://secure.booking.com/myreservations.html?scope=past",
        "<main data-testid='bookings-empty-state'>No past stays</main>",
        "",
    )

    result = BookingComAccountInventorySource().discover(
        _Browser([upcoming, past, cancelled])
    )

    assert result.completeness is InventoryCompleteness.COMPLETE


def test_non_navigable_scope_buttons_cannot_prove_complete_inventory() -> None:
    page = PageContent(
        "https://secure.booking.com/myreservations.html",
        """
        <main data-testid="bookings-empty-state">No upcoming stays</main>
        <button role="tab">Past</button>
        <button role="tab">Cancelled</button>
        """,
        "",
    )

    result = BookingComAccountInventorySource().discover(_Browser([page]))

    assert result.completeness is InventoryCompleteness.INCOMPLETE
    assert result.failure_code is SynchronizationFailureCode.PAGINATION_INCOMPLETE


def test_unknown_layout_fails_closed() -> None:
    page = PageContent(
        "https://secure.booking.com/myreservations.html",
        "<html><body>unexpected</body></html>",
        "unexpected",
    )

    result = BookingComAccountInventorySource().discover(_Browser([page]))

    assert result.completeness is InventoryCompleteness.FAILED
    assert result.failure_code is SynchronizationFailureCode.UNSUPPORTED_LAYOUT


def test_visible_unidentified_card_cannot_prove_empty_inventory() -> None:
    page = PageContent(
        "https://secure.booking.com/myreservations.html",
        "<main data-testid='bookings-list'>"
        "<article data-testid='reservation-card'>Hotel</article></main>",
        "Hotel",
    )

    result = BookingComAccountInventorySource().discover(_Browser([page]))

    assert result.completeness is InventoryCompleteness.FAILED
    assert result.failure_code is SynchronizationFailureCode.EXTRACTION_AMBIGUOUS


def test_explicit_empty_state_is_a_complete_empty_inventory() -> None:
    page = PageContent(
        "https://secure.booking.com/myreservations.html",
        "<main data-testid='bookings-empty-state' data-inventory-complete='true'>"
        "No reservations</main>",
        "No reservations",
    )

    result = BookingComAccountInventorySource().discover(_Browser([page]))

    assert result.completeness is InventoryCompleteness.COMPLETE
    assert result.observations == ()


def test_empty_upcoming_scope_without_other_scope_evidence_is_incomplete() -> None:
    page = PageContent(
        "https://secure.booking.com/myreservations.html",
        "<main data-testid='bookings-empty-state'>No upcoming reservations</main>",
        "No upcoming reservations",
    )

    result = BookingComAccountInventorySource().discover(_Browser([page]))

    assert result.completeness is InventoryCompleteness.INCOMPLETE
    assert result.failure_code is SynchronizationFailureCode.PAGINATION_INCOMPLETE


def test_discovers_reservation_from_embedded_application_json() -> None:
    page = PageContent(
        "https://secure.booking.com/myreservations.html",
        """
        <main data-testid="bookings-list"
              data-inventory-scopes="upcoming,past,cancelled"></main>
        <script type="application/json">
          {"reservations": [{
            "bookingId": "remote-json",
            "confirmationNumber": "CONF-JSON",
            "status": "confirmed",
            "property": {"name": "JSON Hotel", "id": "hotel-json"},
            "checkIn": "2027-03-01",
            "checkOut": "2027-03-03",
            "roomType": "Suite",
            "bookedTotal": {"amount": "450.00", "currency": "USD"},
            "isRefundable": true,
            "guests": {"adults": 2, "children": 1, "rooms": 1}
          }]}
        </script>
        """,
        "",
    )

    result = BookingComAccountInventorySource().discover(_Browser([page]))

    assert result.completeness is InventoryCompleteness.COMPLETE
    assert result.observations[0].remote_id == "remote-json"
    assert result.observations[0].property_name == "JSON Hotel"
    assert result.observations[0].booked_total is not None
    assert result.observations[0].occupancy is not None


def test_logged_out_inventory_fails_as_auth_required() -> None:
    page = PageContent(
        "https://secure.booking.com/myreservations.html",
        "<main data-testid='bookings-list'></main>",
        "",
    )

    result = BookingComAccountInventorySource().discover(
        _Browser([page], authenticated=False)
    )

    assert result.failure_code is SynchronizationFailureCode.AUTH_REQUIRED


class _DelayedInventoryPage:
    def __init__(self) -> None:
        self.url = "https://secure.booking.com/myreservations.html"
        self.rendered = False
        self.events: list[str] = []

    def goto(self, *_args: object, **_kwargs: object) -> None:
        self.events.append("goto")

    def wait_for_load_state(self, *_args: object, **_kwargs: object) -> None:
        self.events.append("networkidle")

    def wait_for_function(self, *_args: object, **_kwargs: object) -> None:
        self.events.append("inventory-ready")
        self.rendered = True

    def content(self) -> str:
        assert self.rendered, "inventory was snapshotted before dynamic rendering"
        self.events.append("content")
        return (
            "<main data-testid='bookings-empty-state' "
            "data-inventory-complete='true'>No reservations</main>"
        )

    def inner_text(self, _selector: str) -> str:
        assert self.rendered
        self.events.append("text")
        return "No reservations"


def test_interactive_browser_waits_for_dynamic_inventory_before_snapshot() -> None:
    page = _DelayedInventoryPage()
    browser = PlaywrightInteractiveBrowser()
    browser._page = page

    snapshot = browser.open_page(page.url)

    assert "No reservations" in snapshot.html
    assert page.events == [
        "goto",
        "networkidle",
        "inventory-ready",
        "content",
        "text",
    ]
