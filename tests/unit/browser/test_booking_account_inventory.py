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


class _InteractiveInventoryBrowser(_Browser):
    def __init__(
        self,
        pages: list[PageContent],
        scope_pages: dict[str, PageContent],
    ) -> None:
        super().__init__(pages)
        self.scope_pages = scope_pages
        self.selected_scopes: list[str] = []

    def open_inventory_scope(self, scope: str) -> PageContent:
        self.selected_scopes.append(scope)
        return self.scope_pages[scope]


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


def test_booking_status_links_are_not_mistaken_for_inventory_tabs() -> None:
    page = PageContent(
        "https://secure.booking.com/mytrips.html?trip_id=active-trip",
        """
        <a href="/confirmation.en-us.html?reservation=opaque">Confirmed</a>
        <a href="/mybooking_archivedsummary.en-us.html">View canceled booking</a>
        """,
        "Confirmed View canceled booking",
    )
    confirmation = PageContent(
        "https://secure.booking.com/confirmation.en-us.html?reservation=opaque",
        """
        <main data-inventory-complete="true"></main>
        <a href="/confirmation.en-us.html?alternate=opaque">Print confirmation</a>
        <script type="application/json">
          {"bookingId": "booking-1", "status": "confirmed",
           "propertyName": "Hotel", "checkIn": "2027-01-01",
           "checkOut": "2027-01-02"}
        </script>
        """,
        "Confirmed",
    )

    result = BookingComAccountInventorySource().discover(
        _Browser([page, confirmation])
    )

    assert result.completeness is InventoryCompleteness.COMPLETE
    assert result.failure_code is None


def test_traverses_current_mytrips_tabs_and_confirmation_cache() -> None:
    entry = PageContent(
        "https://secure.booking.com/mytrips.html",
        """
        <main>
          <button role="tab">Active</button>
          <button role="tab">Past</button>
          <button role="tab">Canceled</button>
          <a href="/mytrips.html?trip_id=active-trip">Upcoming trip</a>
        </main>
        """,
        "Active Past Canceled",
    )
    empty_past = PageContent(
        entry.url,
        """
        <button role="tab">Active</button>
        <button role="tab">Past</button>
        <button role="tab">Canceled</button>
        """,
        "No past trips",
    )
    empty_cancelled = PageContent(
        entry.url,
        """
        <button role="tab">Active</button>
        <button role="tab">Past</button>
        <button role="tab">Canceled</button>
        """,
        "No canceled trips",
    )
    trip = PageContent(
        "https://secure.booking.com/mytrips.html?trip_id=active-trip",
        '<a href="/confirmation.en-us.html?reservation=opaque">Confirmed</a>',
        "Confirmed",
    )
    confirmation = PageContent(
        "https://secure.booking.com/confirmation.en-us.html?reservation=opaque",
        """
        <div data-testid="ReservationStatus">Confirmed</div>
        <script type="application/json">
        {
          "PostBookingReservation:opaque": {
            "__typename": "PostBookingReservation",
            "identity": {"__ref": "PostBookingReservationIdentity:opaque"},
            "property": {"__ref": "PostBookingProperty:42"},
            "price": {"__ref": "PostBookingReservationPrice:opaque"},
            "reservationCheckinDate": {"__ref": "PostBookingReservationDate:in"},
            "reservationCheckoutDate": {"__ref": "PostBookingReservationDate:out"},
            "reservationStatus": "ReservationConfirmed",
            "roomReservations": [
              {"__ref": "PostBookingRoomReservation:opaque"}
            ],
            "hasNonRefundableRoom": false,
            "numberOfAdults": 2,
            "numberOfChildren": 1,
            "numberOfRooms": 1
          },
          "PostBookingReservationIdentity:opaque": {
            "__typename": "PostBookingReservationIdentity",
            "reservationId": "CONF-APOLLO"
          },
          "PostBookingProperty:42": {
            "__typename": "PostBookingProperty",
            "hotelId": 42,
            "hotelName": "Apollo Hotel",
            "currencyCode": "USD"
          },
          "PostBookingReservationPrice:opaque": {
            "__typename": "PostBookingReservationPrice",
            "userTotalPretty": "US$ 1,234.56"
          },
          "PostBookingReservationDate:in": {
            "__typename": "PostBookingReservationDate",
            "rawDate": "2027-08-10"
          },
          "PostBookingReservationDate:out": {
            "__typename": "PostBookingReservationDate",
            "rawDate": "2027-08-12"
          },
          "PostBookingRoomReservation:opaque": {
            "__typename": "PostBookingRoomReservation",
            "room": {"__ref": "PostBookingRoom:opaque"}
          },
          "PostBookingRoom:opaque": {
            "__typename": "PostBookingRoom",
            "roomName": "King Suite"
          }
        }
        </script>
        """,
        "Confirmed",
    )
    browser = _InteractiveInventoryBrowser(
        [entry, trip, confirmation],
        {"past": empty_past, "cancelled": empty_cancelled},
    )

    result = BookingComAccountInventorySource().discover(browser)

    assert result.completeness is InventoryCompleteness.COMPLETE
    assert browser.selected_scopes == ["cancelled", "past"]
    assert len(result.observations) == 1
    observation = result.observations[0]
    assert observation.remote_id == "CONF-APOLLO"
    assert observation.property_name == "Apollo Hotel"
    assert observation.property_ref == "42"
    assert observation.room_type == "King Suite"
    assert observation.booked_total is not None
    assert str(observation.booked_total.amount) == "1234.56"
    assert observation.refundable is True
    assert observation.occupancy is not None


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


class _RedirectedInventoryPage(_DelayedInventoryPage):
    def __init__(self) -> None:
        super().__init__()
        self.url = "https://secure.booking.com/mytrips.html"


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


def test_interactive_browser_waits_when_inventory_entry_redirects() -> None:
    page = _RedirectedInventoryPage()
    browser = PlaywrightInteractiveBrowser()
    browser._page = page

    browser.open_page("https://secure.booking.com/myreservations.html")

    assert "inventory-ready" in page.events
