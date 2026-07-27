from __future__ import annotations

import json
from datetime import UTC, date, datetime
from html.parser import HTMLParser
from typing import Any
from urllib.parse import urljoin, urlparse

from booksaver.application.ports import PageContent
from booksaver.domain.account_sync import (
    InventoryCompleteness,
    InventoryDiscoveryResult,
    ReservationLifecycle,
    ReservationObservation,
    SynchronizationFailureCode,
)
from booksaver.domain.value_objects import Money, Occupancy

_INVENTORY_URL = "https://secure.booking.com/myreservations.html"
_MAX_PAGES = 20
_MAX_RESERVATIONS = 500
_REQUIRED_SCOPES = frozenset({"upcoming", "past", "cancelled"})


class _InventoryParser(HTMLParser):
    def __init__(self, source_url: str) -> None:
        super().__init__(convert_charrefs=True)
        self.source_url = source_url
        self.cards: list[dict[str, str]] = []
        self.next_url: str | None = None
        self.scope_urls: dict[str, str] = {}
        self.scope_controls: set[str] = set()
        self.recognized_inventory = False
        self.recognized_empty = False
        self.explicit_complete = False
        self._json_depth = 0
        self._json_chunks: list[str] = []
        self.json_documents: list[Any] = []
        self._control_depth = 0
        self._control_attrs: dict[str, str] = {}
        self._control_text: list[str] = []

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        values = {key: value or "" for key, value in attrs}
        testid = values.get("data-testid", "")
        declared_scopes = {
            scope.strip().lower()
            for scope in values.get("data-inventory-scopes", "").split(",")
            if scope.strip()
        }
        if (
            values.get("data-inventory-complete", "").lower() == "true"
            or _REQUIRED_SCOPES.issubset(declared_scopes)
        ):
            self.explicit_complete = True
        if testid in {"bookings-list", "reservation-list", "my-bookings-list"}:
            self.recognized_inventory = True
        if testid in {"bookings-empty-state", "reservation-empty-state"}:
            self.recognized_inventory = True
            self.recognized_empty = True
        if testid in {"reservation-card", "booking-card"}:
            self.recognized_inventory = True
            self.cards.append(values)
        if tag == "a" and (
            values.get("rel") == "next"
            or testid in {"pagination-next", "bookings-pagination-next"}
        ):
            href = values.get("href")
            if href:
                self.next_url = urljoin(self.source_url, href)
        if self._control_depth:
            self._control_depth += 1
        elif tag in {"a", "button"} or values.get("role") == "tab":
            self._control_depth = 1
            self._control_attrs = values
            self._control_text = []
        if tag == "script" and values.get("type", "").lower() in {
            "application/ld+json",
            "application/json",
        }:
            self._json_depth = 1
            self._json_chunks = []
        elif self._json_depth:
            self._json_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if self._control_depth:
            self._control_depth -= 1
            if self._control_depth == 0:
                self._register_scope_control()
        if self._json_depth:
            self._json_depth -= 1
            if tag == "script" and self._json_depth == 0:
                try:
                    self.json_documents.append(json.loads("".join(self._json_chunks)))
                except (TypeError, ValueError):
                    pass

    def handle_data(self, data: str) -> None:
        if self._control_depth:
            self._control_text.append(data)
        if self._json_depth:
            self._json_chunks.append(data)

    def _register_scope_control(self) -> None:
        evidence = " ".join(
            [
                *self._control_attrs.values(),
                " ".join(self._control_text),
            ]
        ).lower()
        target = (
            self._control_attrs.get("href")
            or self._control_attrs.get("data-href")
            or self._control_attrs.get("data-url")
        )
        for scope in _REQUIRED_SCOPES:
            aliases = {scope}
            if scope == "past":
                aliases.update({"completed", "previous"})
            if any(alias in evidence for alias in aliases):
                self.scope_controls.add(scope)
                if target:
                    self.scope_urls[scope] = urljoin(self.source_url, target)


class BookingComAccountInventorySource:
    """Scripted, read-only account inventory adapter (ADRs 027-028).

    The DOM-card attributes are a narrow adapter contract covered by fixtures.
    JSON-LD ``LodgingReservation`` is accepted as an additional structured
    source. Unknown layouts are incomplete rather than guessed.
    """

    def discover(self, browser: Any) -> InventoryDiscoveryResult:
        pending: list[tuple[str, str]] = [(_INVENTORY_URL, "upcoming")]
        visited: set[str] = set()
        visited_scopes: set[str] = set()
        observations: dict[str, ReservationObservation] = {}
        explicit_complete = False

        try:
            while pending and len(visited) < _MAX_PAGES:
                url, scope = pending.pop(0)
                if url in visited:
                    continue
                if not _allowlisted(url):
                    return InventoryDiscoveryResult(
                        tuple(observations.values()),
                        InventoryCompleteness.INCOMPLETE,
                        SynchronizationFailureCode.PAGINATION_INCOMPLETE,
                        "Booking.com reservation pagination did not complete.",
                    )
                visited.add(url)
                page: PageContent = browser.open_page(url)
                if not browser.is_authenticated():
                    return InventoryDiscoveryResult.failed(
                        SynchronizationFailureCode.AUTH_REQUIRED,
                        "Booking.com account authentication is required.",
                    )
                parser = _InventoryParser(page.url)
                parser.feed(page.html)
                page_observations = _parse_page(parser, page.url)
                explicit_complete = explicit_complete or parser.explicit_complete
                unidentified_cards = [
                    card
                    for card in parser.cards
                    if not (
                        card.get("data-reservation-id")
                        or card.get("data-booking-id")
                        or card.get("data-confirmation-id")
                    )
                ]
                if unidentified_cards and len(page_observations) < len(parser.cards):
                    return InventoryDiscoveryResult.failed(
                        SynchronizationFailureCode.EXTRACTION_AMBIGUOUS,
                        "Booking.com reservations were visible but could not be identified.",
                    )
                for observation in page_observations:
                    existing = observations.get(observation.remote_id)
                    if (
                        existing is not None
                        and existing.lifecycle is not ReservationLifecycle.UNKNOWN
                        and observation.lifecycle is not ReservationLifecycle.UNKNOWN
                        and existing.lifecycle is not observation.lifecycle
                    ):
                        return InventoryDiscoveryResult.failed(
                            SynchronizationFailureCode.IDENTITY_AMBIGUOUS,
                            "Booking.com returned conflicting reservation identities.",
                        )
                    if (
                        existing is None
                        or _fact_count(observation) > _fact_count(existing)
                    ):
                        observations[observation.remote_id] = observation
                if len(observations) > _MAX_RESERVATIONS:
                    return InventoryDiscoveryResult(
                        tuple(list(observations.values())[:_MAX_RESERVATIONS]),
                        InventoryCompleteness.INCOMPLETE,
                        SynchronizationFailureCode.PAGINATION_INCOMPLETE,
                        "Booking.com returned more reservations than the safe limit.",
                    )
                if not page_observations and not parser.recognized_empty:
                    code = (
                        SynchronizationFailureCode.EXTRACTION_AMBIGUOUS
                        if parser.recognized_inventory
                        else SynchronizationFailureCode.UNSUPPORTED_LAYOUT
                    )
                    return InventoryDiscoveryResult.failed(
                        code,
                        "Booking.com reservation inventory layout was not recognized.",
                    )
                visited_scopes.add(scope)
                if parser.next_url is not None and parser.next_url not in visited:
                    pending.append((parser.next_url, scope))
                for candidate_scope, candidate_url in sorted(
                    parser.scope_urls.items()
                ):
                    if candidate_url not in visited:
                        pending.append((candidate_url, candidate_scope))
        except Exception:
            return InventoryDiscoveryResult.failed(
                SynchronizationFailureCode.NAVIGATION_FAILED,
                "Booking.com reservation inventory could not be read.",
            )

        if pending:
            return InventoryDiscoveryResult(
                tuple(observations.values()),
                InventoryCompleteness.INCOMPLETE,
                SynchronizationFailureCode.PAGINATION_INCOMPLETE,
                "Booking.com reservation pagination did not reach a terminal page.",
            )
        missing_scopes = _REQUIRED_SCOPES - visited_scopes
        if not explicit_complete and missing_scopes:
            return InventoryDiscoveryResult(
                tuple(observations.values()),
                InventoryCompleteness.INCOMPLETE,
                SynchronizationFailureCode.PAGINATION_INCOMPLETE,
                "Booking.com did not prove complete upcoming, past, and cancelled inventory.",
            )
        return InventoryDiscoveryResult(
            tuple(observations.values()), InventoryCompleteness.COMPLETE
        )


def _allowlisted(url: str) -> bool:
    parsed = urlparse(url)
    hostname = (parsed.hostname or "").lower()
    return (
        parsed.scheme == "https"
        and (hostname == "booking.com" or hostname.endswith(".booking.com"))
        and "myreservations" in parsed.path.lower()
    )


def _parse_page(
    parser: _InventoryParser, source_url: str
) -> list[ReservationObservation]:
    observations: dict[str, ReservationObservation] = {}
    for card in parser.cards:
        observation = _observation_from_mapping(card, source_url)
        if observation is not None:
            observations[observation.remote_id] = observation
    for document in parser.json_documents:
        for item in _walk_json(document):
            observation = (
                _observation_from_json_ld(item, source_url)
                if item.get("@type") in {"LodgingReservation", "Reservation"}
                else _observation_from_generic_json(item, source_url)
            )
            if observation is not None:
                existing = observations.get(observation.remote_id)
                if existing is None or _fact_count(observation) > _fact_count(existing):
                    observations[observation.remote_id] = observation
                parser.recognized_inventory = True
    return list(observations.values())


def _observation_from_mapping(
    values: dict[str, str], source_url: str
) -> ReservationObservation | None:
    remote_id = (
        values.get("data-reservation-id")
        or values.get("data-booking-id")
        or values.get("data-confirmation-id")
    )
    if not remote_id:
        return None
    total = _money(
        values.get("data-total-amount"), values.get("data-currency")
    )
    return ReservationObservation(
        remote_id=remote_id,
        confirmation_id=values.get("data-confirmation-id") or None,
        lifecycle=_lifecycle(values.get("data-status")),
        property_name=values.get("data-property-name") or None,
        property_ref=values.get("data-property-url") or None,
        check_in=_date(values.get("data-checkin")),
        check_out=_date(values.get("data-checkout")),
        room_type=values.get("data-room-type") or None,
        booked_total=total,
        refundable=_bool(values.get("data-refundable")),
        refund_note=values.get("data-refund-note", ""),
        refund_deadline=_date(values.get("data-refund-deadline")),
        occupancy=_occupancy(values),
        observed_at=datetime.now(UTC),
        source_url=source_url,
    )


def _observation_from_json_ld(
    item: dict[str, Any], source_url: str
) -> ReservationObservation | None:
    remote_id = item.get("reservationId") or item.get("reservationNumber")
    if not isinstance(remote_id, str) or not remote_id.strip():
        return None
    reserved = item.get("reservationFor")
    reserved = reserved if isinstance(reserved, dict) else {}
    price = item.get("totalPrice") or item.get("price")
    currency = item.get("priceCurrency")
    return ReservationObservation(
        remote_id=remote_id,
        confirmation_id=_string(item.get("reservationNumber")),
        lifecycle=_lifecycle(_string(item.get("reservationStatus"))),
        property_name=_string(reserved.get("name")),
        property_ref=_string(reserved.get("url")),
        check_in=_date(_string(item.get("checkinTime") or item.get("checkInTime"))),
        check_out=_date(_string(item.get("checkoutTime") or item.get("checkOutTime"))),
        room_type=_string(item.get("reservationForName") or item.get("roomType")),
        booked_total=_money(_string(price), _string(currency)),
        refundable=_bool(_string(item.get("refundable"))),
        refund_note=_string(item.get("cancellationPolicy")) or "",
        occupancy=None,
        observed_at=datetime.now(UTC),
        source_url=source_url,
    )


def _observation_from_generic_json(
    item: dict[str, Any], source_url: str
) -> ReservationObservation | None:
    remote_id = _first_string(
        item,
        "reservationId",
        "reservation_id",
        "bookingId",
        "booking_id",
        "reservationNumber",
        "confirmationNumber",
        "confirmationId",
    )
    if remote_id is None:
        return None
    property_data = _first_mapping(
        item, "property", "hotel", "accommodation", "reservationFor"
    )
    total_data = _first_mapping(item, "totalPrice", "bookedTotal", "price")
    total_amount = _first_string(
        item, "totalAmount", "amount", "bookedAmount", "totalPrice"
    )
    currency = _first_string(item, "currency", "priceCurrency", "currencyCode")
    if total_data is not None:
        total_amount = total_amount or _first_string(
            total_data, "amount", "value", "total"
        )
        currency = currency or _first_string(
            total_data, "currency", "currencyCode", "code"
        )
    property_name = _first_string(item, "propertyName", "hotelName")
    property_ref = _first_string(item, "propertyUrl", "hotelUrl")
    if property_data is not None:
        property_name = property_name or _first_string(property_data, "name", "title")
        property_ref = property_ref or _first_string(
            property_data, "url", "id", "propertyId"
        )
    occupancy_data = _first_mapping(item, "occupancy", "guests", "guestCounts")
    return ReservationObservation(
        remote_id=remote_id,
        confirmation_id=_first_string(
            item, "confirmationId", "confirmationNumber", "reservationNumber"
        ),
        lifecycle=_lifecycle(
            _first_string(item, "status", "reservationStatus", "bookingStatus")
        ),
        property_name=property_name,
        property_ref=property_ref,
        check_in=_date(
            _first_string(item, "checkIn", "checkin", "check_in", "checkinTime")
        ),
        check_out=_date(
            _first_string(item, "checkOut", "checkout", "check_out", "checkoutTime")
        ),
        room_type=_first_string(
            item, "roomType", "roomName", "accommodationUnitName"
        ),
        booked_total=_money(total_amount, currency),
        refundable=_first_bool(item, "refundable", "isRefundable"),
        refund_note=_first_string(
            item, "cancellationPolicy", "refundNote", "cancellationText"
        )
        or "",
        refund_deadline=_date(
            _first_string(item, "refundDeadline", "freeCancellationUntil")
        ),
        occupancy=_occupancy_from_json(occupancy_data or item),
        observed_at=datetime.now(UTC),
        source_url=source_url,
        extraction_method="embedded_json",
    )


def _fact_count(observation: ReservationObservation) -> int:
    return sum(
        value is not None and value != ""
        for value in (
            observation.confirmation_id,
            observation.property_name,
            observation.property_ref,
            observation.check_in,
            observation.check_out,
            observation.room_type,
            observation.booked_total,
            observation.refundable,
            observation.occupancy,
        )
    )


def _walk_json(value: Any) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    if isinstance(value, dict):
        found.append(value)
        for nested in value.values():
            if isinstance(nested, (dict, list)):
                found.extend(_walk_json(nested))
    elif isinstance(value, list):
        for item in value:
            found.extend(_walk_json(item))
    return found


def _lifecycle(raw: str | None) -> ReservationLifecycle:
    value = (raw or "").lower()
    if "cancel" in value:
        return ReservationLifecycle.CANCELLED
    if any(token in value for token in ("complete", "past", "checkout")):
        return ReservationLifecycle.COMPLETED
    if "current" in value or "checked_in" in value:
        return ReservationLifecycle.CURRENT
    if any(
        token in value
        for token in ("upcoming", "active", "confirmed", "reservationconfirmed")
    ):
        return ReservationLifecycle.UPCOMING
    return ReservationLifecycle.UNKNOWN


def _date(raw: str | None) -> date | None:
    if not raw:
        return None
    try:
        return date.fromisoformat(raw[:10])
    except ValueError:
        return None


def _money(amount: str | None, currency: str | None) -> Money | None:
    if not amount or not currency:
        return None
    try:
        return Money.of(amount, currency)
    except ValueError:
        return None


def _bool(raw: str | None) -> bool | None:
    if raw is None or raw == "":
        return None
    value = raw.lower()
    if value in {"1", "true", "yes", "refundable"}:
        return True
    if value in {"0", "false", "no", "non_refundable", "non-refundable"}:
        return False
    return None


def _occupancy(values: dict[str, str]) -> Occupancy | None:
    try:
        adults = int(values["data-adults"])
        children = int(values.get("data-children", "0"))
        rooms = int(values.get("data-rooms", "1"))
        return Occupancy(adults, children, rooms)
    except (KeyError, ValueError):
        return None


def _occupancy_from_json(item: dict[str, Any]) -> Occupancy | None:
    adults = _first_int(item, "adults", "adultCount", "numberOfAdults")
    if adults is None:
        return None
    try:
        return Occupancy(
            adults,
            _first_int(item, "children", "childCount", "numberOfChildren") or 0,
            _first_int(item, "rooms", "roomCount", "numberOfRooms") or 1,
        )
    except ValueError:
        return None


def _first_string(item: dict[str, Any], *keys: str) -> str | None:
    for key in keys:
        value = item.get(key)
        if isinstance(value, (str, int, float)) and str(value).strip():
            return str(value)
    return None


def _first_mapping(item: dict[str, Any], *keys: str) -> dict[str, Any] | None:
    for key in keys:
        value = item.get(key)
        if isinstance(value, dict):
            return value
    return None


def _first_int(item: dict[str, Any], *keys: str) -> int | None:
    raw = _first_string(item, *keys)
    try:
        return int(raw) if raw is not None else None
    except ValueError:
        return None


def _first_bool(item: dict[str, Any], *keys: str) -> bool | None:
    for key in keys:
        value = item.get(key)
        if isinstance(value, bool):
            return value
        parsed = _bool(_string(value))
        if parsed is not None:
            return parsed
    return None


def _string(value: Any) -> str | None:
    return value if isinstance(value, str) and value.strip() else None
