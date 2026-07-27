from __future__ import annotations

import json
import re
from datetime import UTC, date, datetime
from html.parser import HTMLParser
from typing import Any
from urllib.parse import urljoin, urlparse

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
        self.detail_urls: set[str] = set()
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
        if tag == "a":
            target = (
                values.get("href")
                or values.get("data-href")
                or values.get("data-url")
            )
            if target:
                candidate = urljoin(self.source_url, target)
                lowered = candidate.lower()
                if "trip_id=" in lowered or "/confirmation" in lowered:
                    self.detail_urls.add(candidate)
                    self.recognized_inventory = True
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
        target = (
            self._control_attrs.get("href")
            or self._control_attrs.get("data-href")
            or self._control_attrs.get("data-url")
        )
        testid = self._control_attrs.get("data-testid", "").lower()
        target_path = urlparse(urljoin(self.source_url, target)).path.lower() if target else ""
        is_scope_control = (
            self._control_attrs.get("role", "").lower() == "tab"
            or "tab" in testid
            or "myreservations" in target_path
            or "mytrips" in target_path
        )
        if not is_scope_control:
            return
        evidence = " ".join(
            [
                *self._control_attrs.values(),
                " ".join(self._control_text),
            ]
        ).lower()
        for scope in _REQUIRED_SCOPES:
            aliases = {scope}
            if scope == "upcoming":
                aliases.add("active")
            if scope == "past":
                aliases.update({"completed", "previous"})
            if scope == "cancelled":
                aliases.add("canceled")
            if any(alias in evidence for alias in aliases):
                self.scope_controls.add(scope)
                self.recognized_inventory = True
                if target:
                    self.scope_urls[scope] = urljoin(self.source_url, target)


class BookingComAccountInventorySource:
    """Scripted, read-only account inventory adapter (ADRs 027-028).

    The DOM-card attributes are a narrow adapter contract covered by fixtures.
    JSON-LD ``LodgingReservation`` is accepted as an additional structured
    source. Unknown layouts are incomplete rather than guessed.
    """

    def discover(self, browser: Any) -> InventoryDiscoveryResult:
        pending: list[tuple[str, str, str]] = [
            ("url", _INVENTORY_URL, "upcoming")
        ]
        visited: set[tuple[str, str, str]] = set()
        visited_scopes: set[str] = set()
        observations: dict[str, ReservationObservation] = {}
        explicit_complete = False

        try:
            while pending and len(visited) < _MAX_PAGES:
                work_kind, target, scope = pending.pop(0)
                work_key = (work_kind, target, scope)
                if work_key in visited:
                    continue
                if work_kind == "url" and not _allowlisted(target):
                    return InventoryDiscoveryResult(
                        tuple(observations.values()),
                        InventoryCompleteness.INCOMPLETE,
                        SynchronizationFailureCode.PAGINATION_INCOMPLETE,
                        "Booking.com reservation pagination did not complete.",
                    )
                visited.add(work_key)
                if work_kind == "scope":
                    page = browser.open_inventory_scope(scope)
                else:
                    page = browser.open_page(target)
                if not browser.is_authenticated():
                    return InventoryDiscoveryResult.failed(
                        SynchronizationFailureCode.AUTH_REQUIRED,
                        "Booking.com account authentication is required.",
                    )
                parser = _InventoryParser(page.url)
                parser.feed(page.html)
                if _looks_like_empty_scope(page.text, scope):
                    parser.recognized_inventory = True
                    parser.recognized_empty = True
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
                is_navigation_container = bool(
                    parser.scope_controls or parser.detail_urls
                )
                if (
                    not page_observations
                    and not parser.recognized_empty
                    and not is_navigation_container
                ):
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
                if parser.next_url is not None:
                    pending.append(("url", parser.next_url, scope))
                for candidate_scope, candidate_url in sorted(
                    parser.scope_urls.items()
                ):
                    pending.append(("url", candidate_url, candidate_scope))
                interactive_scopes = sorted(
                    parser.scope_controls - parser.scope_urls.keys() - visited_scopes
                )
                if interactive_scopes and not hasattr(browser, "open_inventory_scope"):
                    continue
                for candidate_scope in interactive_scopes:
                    pending.append(("scope", candidate_scope, candidate_scope))
                for detail_url in sorted(parser.detail_urls):
                    pending.append(("url", detail_url, scope))
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
        and (
            "myreservations" in parsed.path.lower()
            or "mytrips" in parsed.path.lower()
            or parsed.path.lower().startswith("/confirmation")
        )
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
        for observation in _observations_from_apollo_cache(document, source_url):
            observations[observation.remote_id] = observation
            parser.recognized_inventory = True
        for item in _walk_json(document):
            observation = (
                _observation_from_json_ld(item, source_url)
                if item.get("@type") in {"LodgingReservation", "Reservation"}
                else _observation_from_generic_json(item, source_url)
            )
            if observation is not None and (
                item.get("@type") in {"LodgingReservation", "Reservation"}
                or _fact_count(observation) >= 2
            ):
                existing = observations.get(observation.remote_id)
                if existing is None or _fact_count(observation) > _fact_count(existing):
                    observations[observation.remote_id] = observation
                parser.recognized_inventory = True
    return list(observations.values())


def _observations_from_apollo_cache(
    document: Any, source_url: str
) -> list[ReservationObservation]:
    if not isinstance(document, dict):
        return []
    entities = [
        value
        for value in document.values()
        if isinstance(value, dict)
        and value.get("__typename") == "PostBookingReservation"
    ]
    observations: list[ReservationObservation] = []
    for entity in entities:
        identity = _resolve_cache_value(document, entity.get("identity"))
        property_data = _resolve_cache_value(document, entity.get("property"))
        price = _resolve_cache_value(document, entity.get("price"))
        check_in = _resolve_cache_value(
            document, entity.get("reservationCheckinDate")
        )
        check_out = _resolve_cache_value(
            document, entity.get("reservationCheckoutDate")
        )
        remote_id = _first_string(identity, "reservationId", "reservationNumber")
        if remote_id is None:
            continue
        property_name = _first_string(property_data, "hotelName", "name")
        property_ref = _first_string(
            property_data, "url", "hotelId", "propertyId"
        )
        room_type = _apollo_room_type(document, entity)
        currency = (
            _first_string(price, "currency", "currencyCode")
            or _first_string(property_data, "currencyCode")
            or _deep_first_string(
                _resolve_cache_value(document, entity), "selectedCurrency"
            )
        )
        total_text = _first_string(
            price,
            "userTotal",
            "total",
            "userTotalPretty",
            "totalPretty",
        )
        non_refundable = _first_bool(entity, "hasNonRefundableRoom")
        refundable = None if non_refundable is None else not non_refundable
        resolved = _resolve_cache_value(document, entity)
        observations.append(
            ReservationObservation(
                remote_id=remote_id,
                confirmation_id=remote_id,
                lifecycle=_lifecycle(
                    _first_string(
                        entity,
                        "reservationStatus",
                        "confirmedStatus",
                        "status",
                    )
                ),
                property_name=property_name,
                property_ref=property_ref,
                check_in=_date(_first_string(check_in, "rawDate", "date")),
                check_out=_date(_first_string(check_out, "rawDate", "date")),
                room_type=room_type,
                booked_total=_money(_amount_text(total_text), currency),
                refundable=refundable,
                refund_note=_first_string(
                    entity, "cancellationType", "cancellationPolicy"
                )
                or "",
                occupancy=_occupancy_from_apollo(resolved),
                observed_at=datetime.now(UTC),
                source_url=source_url,
                extraction_method="apollo_cache",
            )
        )
    return observations


def _resolve_cache_value(
    cache: dict[str, Any],
    value: Any,
    *,
    visited: frozenset[str] = frozenset(),
    depth: int = 0,
) -> Any:
    if depth > 12:
        return {}
    if isinstance(value, dict):
        reference = value.get("__ref")
        if isinstance(reference, str):
            if reference in visited:
                return {}
            return _resolve_cache_value(
                cache,
                cache.get(reference, {}),
                visited=visited | {reference},
                depth=depth + 1,
            )
        return {
            key: _resolve_cache_value(
                cache, nested, visited=visited, depth=depth + 1
            )
            for key, nested in value.items()
        }
    if isinstance(value, list):
        return [
            _resolve_cache_value(cache, item, visited=visited, depth=depth + 1)
            for item in value
        ]
    return value


def _apollo_room_type(cache: dict[str, Any], entity: dict[str, Any]) -> str | None:
    room_reservations = entity.get("roomReservations")
    if isinstance(room_reservations, list):
        for raw_reservation in room_reservations:
            reservation = _resolve_cache_value(cache, raw_reservation)
            room = _resolve_cache_value(cache, reservation.get("room"))
            name = _first_string(room, "roomName", "name")
            if name:
                return name
    room_types = _resolve_cache_value(cache, entity.get("roomTypes"))
    if isinstance(room_types, list):
        for room_type in room_types:
            if isinstance(room_type, str) and room_type.strip():
                return room_type
            if isinstance(room_type, dict):
                name = _first_string(room_type, "roomName", "name")
                if name:
                    return name
    return None


def _deep_first_string(value: Any, *keys: str) -> str | None:
    if isinstance(value, dict):
        direct = _first_string(value, *keys)
        if direct:
            return direct
        for nested in value.values():
            found = _deep_first_string(nested, *keys)
            if found:
                return found
    elif isinstance(value, list):
        for nested in value:
            found = _deep_first_string(nested, *keys)
            if found:
                return found
    return None


def _deep_first_int(value: Any, *keys: str) -> int | None:
    if isinstance(value, dict):
        direct = _first_int(value, *keys)
        if direct is not None:
            return direct
        for nested in value.values():
            found = _deep_first_int(nested, *keys)
            if found is not None:
                return found
    elif isinstance(value, list):
        for nested in value:
            found = _deep_first_int(nested, *keys)
            if found is not None:
                return found
    return None


def _occupancy_from_apollo(value: Any) -> Occupancy | None:
    adults = _deep_first_int(
        value, "adults", "adultCount", "numberOfAdults", "numberOfAdultGuests"
    )
    if adults is None:
        return None
    try:
        return Occupancy(
            adults,
            _deep_first_int(
                value,
                "children",
                "childCount",
                "numberOfChildren",
                "numberOfChildGuests",
            )
            or 0,
            _deep_first_int(value, "rooms", "roomCount", "numberOfRooms") or 1,
        )
    except ValueError:
        return None


def _amount_text(raw: str | None) -> str | None:
    if not raw:
        return None
    value = re.sub(r"[^\d,.\-]", "", raw)
    if "," in value and "." in value:
        if value.rfind(".") > value.rfind(","):
            value = value.replace(",", "")
        else:
            value = value.replace(".", "").replace(",", ".")
    elif "," in value:
        pieces = value.split(",")
        value = "".join(pieces) if len(pieces[-1]) == 3 else ".".join(pieces)
    return value or None


def _looks_like_empty_scope(text: str, scope: str) -> bool:
    normalized = " ".join(text.lower().split())
    aliases = {
        "upcoming": ("active", "upcoming"),
        "past": ("past", "previous"),
        "cancelled": ("canceled", "cancelled"),
    }[scope]
    return any(
        phrase in normalized
        for alias in aliases
        for phrase in (
            f"no {alias} bookings",
            f"no {alias} trips",
            f"no {alias} reservations",
            f"no {alias} stays",
        )
    )


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
