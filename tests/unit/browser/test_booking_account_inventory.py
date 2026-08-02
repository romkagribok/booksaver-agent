from datetime import UTC, date, datetime

import pytest

from booksaver.application.ports import PageContent
from booksaver.domain.account_sync import (
    InventoryCompleteness,
    InventoryRecoveryOutcome,
    ReservationLifecycle,
    ReservationObservation,
    SynchronizationFailureCode,
    evaluate_eligibility,
)
from booksaver.domain.agent import (
    AgentAction,
    AgentActionType,
    AgentBudget,
    AgentSettings,
    AgentStopReason,
    BudgetExceeded,
    ElementInfo,
    EscalationResult,
    Observation,
)
from booksaver.domain.errors import UserKeyInvalidError
from booksaver.domain.value_objects import Money, Occupancy
from booksaver.infrastructure.browser.booking_account_inventory import (
    BookingComAccountInventorySource,
    _inventory_recovery_verified,
    _InventoryGuardedBrowser,
)
from booksaver.infrastructure.browser.playwright_adapter import (
    PlaywrightInteractiveBrowser,
)
from booksaver.monitor.browser_agent import BrowserAgent
from booksaver.monitor.trace import TraceRecorder


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


def _interpreted_observation(
    *, lifecycle: ReservationLifecycle = ReservationLifecycle.UPCOMING
) -> ReservationObservation:
    return ReservationObservation(
        remote_id="llm-remote-1",
        lifecycle=lifecycle,
        observed_at=datetime(2026, 8, 2, tzinfo=UTC),
        confirmation_id="CONF-LLM",
        property_name="Recovered Hotel",
        property_ref="recovered-hotel",
        check_in=date(2027, 1, 10),
        check_out=date(2027, 1, 12),
        room_type="King room",
        booked_total=Money.of("200", "USD"),
        refundable=True,
        occupancy=Occupancy(2, 0, 1),
    )


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
    cancelled = PageContent(
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

    result = BookingComAccountInventorySource().discover(
        _Browser([first, cancelled, past])
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
        "https://secure.booking.com/myreservations.html?scope=past",
        "<main data-testid='bookings-empty-state'>No past stays</main>",
        "",
    )
    cancelled = PageContent(
        "https://secure.booking.com/myreservations.html?scope=cancelled",
        "<main data-testid='bookings-empty-state'>No cancelled stays</main>",
        "",
    )

    result = BookingComAccountInventorySource().discover(
        _Browser([upcoming, cancelled, past])
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
            "hotelName": {
              "__typename": "Translation",
              "rawValue": "Apollo Hotel",
              "translation": "Apollo Hotel"
            },
            "currencyCode": "USD"
          },
          "PostBookingReservationPrice:opaque": {
            "__typename": "PostBookingReservationPrice",
            "userTotalPretty": "US$ 1,234.56"
          },
          "PostBookingReservationDate:in": {
            "__typename": "PostBookingReservationDate",
            "rawDate": 1817856000
          },
          "PostBookingReservationDate:out": {
            "__typename": "PostBookingReservationDate",
            "rawDate": 1818028800
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
        "Confirmed · 2 adults · 1 child · 1 room",
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
    assert observation.check_in is not None
    assert observation.check_in.isoformat() == "2027-08-10"
    assert observation.check_out is not None
    assert observation.check_out.isoformat() == "2027-08-12"
    assert observation.booked_total is not None
    assert str(observation.booked_total.amount) == "1234.56"
    assert observation.refundable is True
    assert observation.occupancy is not None
    assert observation.occupancy.adults == 2
    assert observation.occupancy.children == 1


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


def test_interpreted_unidentified_card_cannot_prove_complete_inventory() -> None:
    class Interpreter:
        def interpret(
            self, _page_text: str, _source_url: str
        ) -> tuple[ReservationObservation, ...]:
            return (_interpreted_observation(),)

    page = PageContent(
        "https://secure.booking.com/myreservations.html",
        "<main data-testid='bookings-list' data-inventory-complete='true'>"
        "<article data-testid='reservation-card'>Recovered Hotel</article></main>",
        "Reservation llm-remote-1 at Recovered Hotel",
    )

    result = BookingComAccountInventorySource(
        interpreter=Interpreter(),
        consume_interpreter_call=lambda: None,
    ).discover(_Browser([page]))

    assert result.completeness is InventoryCompleteness.INCOMPLETE
    assert result.failure_code is SynchronizationFailureCode.EXTRACTION_AMBIGUOUS
    assert result.observations[0].remote_id == "llm-remote-1"


def test_button_only_pagination_requires_guarded_recovery() -> None:
    page = PageContent(
        "https://secure.booking.com/myreservations.html",
        """
        <main data-testid="bookings-list" data-inventory-complete="true">
          <article data-testid="reservation-card"
            data-reservation-id="remote-1" data-status="confirmed"
            data-property-name="Hotel One"></article>
          <button data-testid="pagination-next">Load more reservations</button>
        </main>
        """,
        "Hotel One Load more reservations",
    )

    result = BookingComAccountInventorySource().discover(_Browser([page]))

    assert result.completeness is InventoryCompleteness.INCOMPLETE
    assert result.failure_code is SynchronizationFailureCode.PAGINATION_INCOMPLETE


def test_button_only_pagination_runs_named_recovery_to_terminal_page() -> None:
    attempted_steps: list[str] = []

    class Browser:
        def __init__(self) -> None:
            self.terminal = False

        def open_page(self, url: str) -> PageContent:
            return PageContent(
                url,
                """
                <main data-testid="bookings-list" data-inventory-complete="true">
                  <article data-testid="reservation-card"
                    data-reservation-id="remote-1" data-status="confirmed"
                    data-confirmation-id="CONF-1" data-property-name="Hotel One"
                    data-property-url="hotel-one" data-checkin="2027-01-10"
                    data-checkout="2027-01-12" data-room-type="King room"
                    data-total-amount="200" data-currency="USD"
                    data-refundable="true" data-adults="2"></article>
                  <button>Load more reservations</button>
                </main>
                """,
                "Hotel One Load more reservations",
            )

        def is_authenticated(self) -> bool:
            return True

        def observe(self) -> Observation:
            return Observation(
                "https://secure.booking.com/myreservations.html",
                "Trips",
                "No upcoming reservations" if self.terminal else "Hotel One",
                ()
                if self.terminal
                else (ElementInfo("e0", "button", "Load more reservations"),),
            )

    browser = Browser()

    class Agent:
        def complete_step(self, step: str, **_kwargs: object) -> EscalationResult:
            attempted_steps.append(step)
            browser.terminal = True
            return EscalationResult(ok=True, detail="done")

    result = BookingComAccountInventorySource(
        recovery_factory=lambda _browser: Agent(),
    ).discover(browser)

    assert result.completeness is InventoryCompleteness.COMPLETE
    assert attempted_steps == ["inventory_upcoming_pagination"]
    assert [item.remote_id for item in result.observations] == ["remote-1"]


def test_inventory_discovery_checks_outer_time_budget_between_pages() -> None:
    first = PageContent(
        "https://secure.booking.com/myreservations.html",
        "<main data-testid='bookings-list' data-inventory-complete='true'>"
        "<article data-testid='reservation-card' data-reservation-id='remote-1' "
        "data-status='confirmed' data-property-name='Hotel One'></article></main>"
        "<a rel='next' href='/myreservations.html?page=2'>Next</a>",
        "Next",
    )
    second = PageContent(
        "https://secure.booking.com/myreservations.html?page=2",
        "<main data-testid='bookings-empty-state'>No reservations</main>",
        "No reservations",
    )
    checks = 0

    def check_time() -> None:
        nonlocal checks
        checks += 1
        if checks >= 4:
            raise BudgetExceeded("check timeout exceeded (61s/60s)")

    browser = _Browser([first, second])
    result = BookingComAccountInventorySource(check_time=check_time).discover(browser)

    assert result.completeness is InventoryCompleteness.FAILED
    assert result.failure_code is SynchronizationFailureCode.NAVIGATION_FAILED
    assert result.recovery_outcome is InventoryRecoveryOutcome.BUDGET_EXHAUSTED
    assert len(browser.pages) == 1


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


def test_unknown_layout_uses_positive_interpreter_without_claiming_completeness() -> None:
    class Interpreter:
        def __init__(self) -> None:
            self.calls = 0

        def interpret(
            self, _page_text: str, _source_url: str
        ) -> tuple[ReservationObservation, ...]:
            self.calls += 1
            return (_interpreted_observation(),)

    interpreter = Interpreter()
    charged = 0

    def charge() -> None:
        nonlocal charged
        charged += 1

    page = PageContent(
        "https://secure.booking.com/myreservations.html",
        "<main>Redesigned reservation card</main>",
        "Reservation llm-remote-1 at Recovered Hotel, January 10 to January 12",
    )
    source = BookingComAccountInventorySource(
        interpreter=interpreter,
        consume_interpreter_call=charge,
        llm_calls_used=lambda: charged,
    )

    result = source.discover(_Browser([page]))

    assert result.completeness is InventoryCompleteness.INCOMPLETE
    assert result.recovery_outcome is InventoryRecoveryOutcome.PARTIAL
    assert result.llm_calls_used == 1
    assert interpreter.calls == 1
    assert result.observations[0].remote_id == "llm-remote-1"
    assert result.observations[0].extraction_method == "llm_inventory"


def test_negative_interpreter_claim_is_rejected() -> None:
    class Interpreter:
        def interpret(
            self, _page_text: str, _source_url: str
        ) -> tuple[ReservationObservation, ...]:
            return (
                _interpreted_observation(
                    lifecycle=ReservationLifecycle.CANCELLED
                ),
            )

    page = PageContent(
        "https://secure.booking.com/myreservations.html",
        "<main>Redesigned reservation card</main>",
        "Reservation status unavailable",
    )
    result = BookingComAccountInventorySource(
        interpreter=Interpreter(),
        consume_interpreter_call=lambda: None,
        llm_calls_used=lambda: 1,
    ).discover(_Browser([page]))

    assert result.completeness is InventoryCompleteness.FAILED
    assert result.observations == ()
    assert result.recovery_outcome is InventoryRecoveryOutcome.GAVE_UP


def test_interpreter_cannot_invent_a_remote_identity_absent_from_page() -> None:
    class Interpreter:
        def interpret(
            self, _page_text: str, _source_url: str
        ) -> tuple[ReservationObservation, ...]:
            return (_interpreted_observation(),)

    page = PageContent(
        "https://secure.booking.com/myreservations.html",
        "<main>Redesigned reservation card</main>",
        "A future stay is visible, but no reservation identity is rendered.",
    )

    result = BookingComAccountInventorySource(
        interpreter=Interpreter(),
        consume_interpreter_call=lambda: None,
        llm_calls_used=lambda: 1,
    ).discover(_Browser([page]))

    assert result.completeness is InventoryCompleteness.FAILED
    assert result.observations == ()
    assert result.recovery_outcome is InventoryRecoveryOutcome.GAVE_UP


def test_captcha_fails_closed_without_invoking_recovery() -> None:
    page = PageContent(
        "https://secure.booking.com/myreservations.html",
        '<main data-inventory-complete="true">Verify</main>',
        "Verify you are human",
    )

    def forbidden_recovery(_browser: object) -> object:
        raise AssertionError("captcha must not invoke the LLM")

    result = BookingComAccountInventorySource(
        recovery_factory=forbidden_recovery,
    ).discover(_Browser([page]))

    assert result.completeness is InventoryCompleteness.FAILED
    assert result.failure_code is SynchronizationFailureCode.BOT_WALL
    assert result.llm_calls_used == 0


def test_agent_recovers_changed_scope_controls_and_completeness_is_verified() -> None:
    observed_labels: list[tuple[str, ...]] = []

    class ScopeBrowser:
        def __init__(self) -> None:
            self.scope = "upcoming"
            self.executed: list[str] = []

        def open_page(self, url: str) -> PageContent:
            return PageContent(
                url,
                "<main>Redesigned trips</main>",
                "No upcoming trips",
            )

        def is_authenticated(self) -> bool:
            return True

        def observe(self) -> Observation:
            text = {
                "upcoming": "No upcoming trips",
                "past": "No past trips",
                "cancelled": "No canceled trips",
            }[self.scope]
            return Observation(
                url="https://secure.booking.com/myreservations.html",
                title="Trips",
                text=text,
                elements=(
                    ElementInfo("e0", "button", "Past"),
                    ElementInfo("e1", "button", "Cancelled"),
                ),
            )

        def act(self, action: AgentAction) -> None:
            self.scope = "past" if action.ref == "e0" else "cancelled"
            self.executed.append(self.scope)

        def screenshot(self) -> bytes:
            return b"png"

    class Brain:
        def decide(self, context: object) -> AgentAction:
            goal = getattr(context, "goal")
            observation = getattr(context, "observation")
            observed_labels.append(tuple(item.label for item in observation.elements))
            return AgentAction(
                AgentActionType.CLICK,
                ref="e0" if "past" in goal else "e1",
            )

    browser = ScopeBrowser()
    budget = AgentBudget(AgentSettings())

    def recovery_factory(guarded_browser: object) -> BrowserAgent:
        return BrowserAgent(
            guarded_browser,  # type: ignore[arg-type]
            Brain(),  # type: ignore[arg-type]
            budget,
            TraceRecorder("inventory-test"),
        )

    result = BookingComAccountInventorySource(
        recovery_factory=recovery_factory,
        llm_calls_used=lambda: budget.llm_calls_used,
    ).discover(browser)

    assert result.completeness is InventoryCompleteness.COMPLETE
    assert result.recovery_outcome is InventoryRecoveryOutcome.RECOVERED
    assert result.llm_calls_used == 2
    assert browser.executed == ["cancelled", "past"]
    assert all("Cancelled" in labels for labels in observed_labels)


def test_persistent_scope_aliases_do_not_false_prove_requested_scope() -> None:
    entry = PageContent(
        "https://secure.booking.com/myreservations.html",
        """
        <main data-testid="bookings-empty-state">No upcoming stays</main>
        <a role="tab" href="/myreservations.html?scope=past">Past</a>
        <a role="tab" href="/myreservations.html?scope=cancelled">Cancelled</a>
        """,
        "No upcoming stays Past Cancelled",
    )
    aliased = PageContent(
        "https://secure.booking.com/myreservations.html",
        entry.html,
        entry.text,
    )

    result = BookingComAccountInventorySource().discover(
        _Browser([entry, aliased, aliased])
    )

    assert result.completeness is InventoryCompleteness.INCOMPLETE
    assert result.failure_code is SynchronizationFailureCode.PAGINATION_INCOMPLETE


def test_unchanged_nearby_scope_words_do_not_verify_recovery() -> None:
    observation = Observation(
        url="https://secure.booking.com/myreservations.html",
        title="Trips",
        text="Past reservations · Upcoming Hotel · confirmation ABC123",
        elements=(ElementInfo("e0", "button", "Past"),),
    )

    class Browser:
        def observe(self) -> Observation:
            return Observation(
                url=observation.url,
                title=observation.title,
                text=observation.text,
                elements=(ElementInfo("e1", "button", "Past"),),
                scroll_y=500,
            )

        def is_authenticated(self) -> bool:
            return True

    assert not _inventory_recovery_verified(
        Browser(),
        "past",
        "past",
        "scope",
        observation,
    )


def test_changed_scope_label_still_attempts_named_recovery() -> None:
    attempted_steps: list[str] = []

    class Browser:
        def open_page(self, url: str) -> PageContent:
            return PageContent(url, "<main>No upcoming trips</main>", "No upcoming trips")

        def is_authenticated(self) -> bool:
            return True

        def observe(self) -> Observation:
            return Observation(
                url="https://secure.booking.com/myreservations.html",
                title="Trips",
                text="No upcoming trips",
                elements=(ElementInfo("e0", "button", "History"),),
            )

    class Agent:
        def complete_step(self, step: str, **_kwargs: object) -> EscalationResult:
            attempted_steps.append(step)
            return EscalationResult(
                ok=False,
                detail="gave up",
                stop_reason=AgentStopReason.NO_PROGRESS,
            )

    result = BookingComAccountInventorySource(
        recovery_factory=lambda _browser: Agent(),
    ).discover(Browser())

    assert result.completeness is InventoryCompleteness.INCOMPLETE
    assert attempted_steps == ["inventory_cancelled_scope"]


@pytest.mark.parametrize(
    ("pages", "expected_step"),
    [
        (
            [
                PageContent(
                    "https://secure.booking.com/myreservations.html",
                    """
                    <main data-testid="bookings-empty-state">No upcoming stays</main>
                    <a rel="next" href="/myreservations.html?page=2">Next</a>
                    <a role="tab" href="/myreservations.html?scope=past">Past</a>
                    <a role="tab" href="/myreservations.html?scope=cancelled">Cancelled</a>
                    """,
                    "No upcoming stays",
                ),
                PageContent(
                    "https://secure.booking.com/myreservations.html?page=2",
                    '<main data-testid="bookings-list"></main>',
                    "Reservation layout changed",
                ),
            ],
            "inventory_upcoming_pagination",
        ),
        (
            [
                PageContent(
                    "https://secure.booking.com/myreservations.html",
                    """
                    <main data-inventory-complete="true"></main>
                    <a href="/confirmation.en-us.html?reservation=opaque">
                      Reservation details
                    </a>
                    """,
                    "Reservation details",
                ),
                PageContent(
                    "https://secure.booking.com/confirmation.en-us.html?reservation=opaque",
                    "<main>Changed detail view</main>",
                    "Changed detail view",
                ),
            ],
            "inventory_upcoming_detail",
        ),
    ],
)
def test_pagination_and_detail_drift_attempt_named_recovery(
    pages: list[PageContent],
    expected_step: str,
) -> None:
    attempted_steps: list[str] = []

    class Browser:
        def __init__(self) -> None:
            self.pages = list(pages)
            self.current: PageContent | None = None

        def open_page(self, _url: str) -> PageContent:
            self.current = self.pages.pop(0)
            return self.current

        def is_authenticated(self) -> bool:
            return True

        def observe(self) -> Observation:
            current = self.current or pages[0]
            return Observation(current.url, "Trips", current.text, ())

    class Agent:
        def complete_step(self, step: str, **_kwargs: object) -> EscalationResult:
            attempted_steps.append(step)
            return EscalationResult(
                ok=False,
                detail="gave up",
                stop_reason=AgentStopReason.NO_PROGRESS,
            )

    result = BookingComAccountInventorySource(
        recovery_factory=lambda _browser: Agent(),
    ).discover(Browser())

    assert result.completeness is InventoryCompleteness.INCOMPLETE
    assert attempted_steps == [expected_step]


@pytest.mark.parametrize("action_type", [AgentActionType.FILL, AgentActionType.SELECT])
def test_inventory_guard_rejects_all_input_actions(
    action_type: AgentActionType,
) -> None:
    class Browser:
        def observe(self) -> Observation:
            return Observation(
                url="https://secure.booking.com/myreservations.html",
                title="Trips",
                text="",
                elements=(ElementInfo("e0", "input", "Search reservations"),),
            )

        def act(self, _action: AgentAction) -> None:
            raise AssertionError("input action reached the shared browser")

    guarded = _InventoryGuardedBrowser(Browser())
    guarded.observe()

    with pytest.raises(RuntimeError, match="refused an input action"):
        guarded.act(AgentAction(action_type, ref="e0", value="unsafe"))


def test_inventory_guard_rejects_generic_and_mutating_buttons() -> None:
    class Browser:
        def observe(self) -> Observation:
            return Observation(
                url="https://secure.booking.com/myreservations.html",
                title="Trips",
                text="",
                elements=(
                    ElementInfo("e0", "button", "Continue"),
                    ElementInfo("e1", "button", "Cancel booking"),
                ),
            )

        def act(self, _action: AgentAction) -> None:
            raise AssertionError("unsafe click reached the shared browser")

    guarded = _InventoryGuardedBrowser(Browser())
    guarded.observe()

    for ref in ("e0", "e1"):
        with pytest.raises(RuntimeError, match="refused a non-read-only control"):
            guarded.act(AgentAction(AgentActionType.CLICK, ref=ref))


def test_inventory_guard_observes_only_successful_read_only_actions() -> None:
    executed: list[AgentAction] = []
    observed: list[AgentAction] = []

    class Browser:
        def observe(self) -> Observation:
            return Observation(
                url="https://secure.booking.com/myreservations.html",
                title="Trips",
                text="",
                elements=(ElementInfo("e0", "button", "Past"),),
            )

        def act(self, action: AgentAction) -> None:
            executed.append(action)

    action = AgentAction(AgentActionType.CLICK, ref="e0")
    guarded = _InventoryGuardedBrowser(Browser(), action_observer=observed.append)
    guarded.observe()
    guarded.act(action)

    assert executed == [action]
    assert observed == [action]


@pytest.mark.parametrize("label", ["Previous bookings (3)", "Cancelled trips 2"])
def test_inventory_guard_allows_scope_labels_with_counts(label: str) -> None:
    executed: list[AgentAction] = []

    class Browser:
        def observe(self) -> Observation:
            return Observation(
                url="https://secure.booking.com/myreservations.html",
                title="Trips",
                text="",
                elements=(ElementInfo("e0", "button", label),),
            )

        def act(self, action: AgentAction) -> None:
            executed.append(action)

    action = AgentAction(AgentActionType.CLICK, ref="e0")
    guarded = _InventoryGuardedBrowser(Browser())
    guarded.observe()
    guarded.act(action)

    assert executed == [action]


def test_inventory_guard_does_not_observe_failed_action() -> None:
    observed: list[AgentAction] = []

    class Browser:
        def observe(self) -> Observation:
            return Observation(
                url="https://secure.booking.com/myreservations.html",
                title="Trips",
                text="",
                elements=(ElementInfo("e0", "button", "Past"),),
            )

        def act(self, _action: AgentAction) -> None:
            raise RuntimeError("browser click failed")

    guarded = _InventoryGuardedBrowser(Browser(), action_observer=observed.append)
    guarded.observe()

    with pytest.raises(RuntimeError, match="browser click failed"):
        guarded.act(AgentAction(AgentActionType.CLICK, ref="e0"))
    assert observed == []


def test_interpreted_identity_cannot_supply_ungrounded_eligibility_facts() -> None:
    class Interpreter:
        def interpret(
            self, _page_text: str, _source_url: str
        ) -> tuple[ReservationObservation, ...]:
            return (_interpreted_observation(),)

    page = PageContent(
        "https://secure.booking.com/myreservations.html",
        "<main>Changed reservation card</main>",
        "Reservation llm-remote-1 is visible.",
    )
    result = BookingComAccountInventorySource(
        interpreter=Interpreter(),
        consume_interpreter_call=lambda: None,
    ).discover(_Browser([page]))

    observation = result.observations[0]
    assert observation.lifecycle is ReservationLifecycle.UNKNOWN
    assert observation.refundable is None
    assert observation.check_in is None
    assert observation.booked_total is None
    assert observation.occupancy is None
    assert not evaluate_eligibility(observation, today=date(2026, 8, 2)).is_eligible


def test_personal_key_error_from_interpreter_is_preserved() -> None:
    class Interpreter:
        def interpret(
            self, _page_text: str, _source_url: str
        ) -> tuple[ReservationObservation, ...]:
            raise UserKeyInvalidError(42)

    source = BookingComAccountInventorySource(
        interpreter=Interpreter(),
        consume_interpreter_call=lambda: None,
    )
    page = PageContent(
        "https://secure.booking.com/myreservations.html",
        "<main>Changed reservation card</main>",
        "Reservation data changed",
    )

    with pytest.raises(UserKeyInvalidError):
        source.discover(_Browser([page]))


def test_personal_key_error_from_navigation_agent_is_preserved() -> None:
    class Browser:
        def open_page(self, url: str) -> PageContent:
            return PageContent(url, "<main>No upcoming trips</main>", "No upcoming trips")

        def is_authenticated(self) -> bool:
            return True

        def observe(self) -> Observation:
            return Observation(
                url="https://secure.booking.com/myreservations.html",
                title="Trips",
                text="No upcoming trips",
                elements=(ElementInfo("e0", "button", "History"),),
            )

    def recovery_factory(_browser: object) -> object:
        raise UserKeyInvalidError(42)

    with pytest.raises(UserKeyInvalidError):
        BookingComAccountInventorySource(
            recovery_factory=recovery_factory,
        ).discover(Browser())


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
