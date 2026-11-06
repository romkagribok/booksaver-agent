"""Code-owned inventory destination classification and reservation evidence mapping."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from enum import Enum
from typing import Any, cast
from urllib.parse import SplitResult, parse_qsl, unquote, urlsplit

from booksaver.domain.account_sync import ReservationLifecycle
from booksaver.domain.browser_executor import (
    AllInEvidence,
    EvidenceCompleteness,
    RefundabilityEvidence,
)
from booksaver.domain.browser_guard import is_booking_destination
from booksaver.domain.inventory_executor import (
    InventoryExecutionStatus,
    InventoryScope,
    ObservedReservation,
)
from booksaver.domain.value_objects import Money, Occupancy

_AUTH_DESTINATION_TEXT = re.compile(
    r"\b(sign\s*in|signin|log\s*in|login|auth|password|passcode|two[- ]factor|mfa)\b",
    re.IGNORECASE,
)
_CHALLENGE_DESTINATION_TEXT = re.compile(
    r"\b(captcha|verify\s*human|challenge|bot\s*wall)\b", re.IGNORECASE
)
_MUTATION_DESTINATION_TEXT = re.compile(
    r"\b(book\s+now|reserve\s+now|pay|payment|purchase|buy|checkout|cancel|delete|"
    r"remove|change|modify|edit|manage|upgrade|extras?|upload|download|account\s+settings|"
    r"profile)\b",
    re.IGNORECASE,
)
_MUTATION_PATH_TEXT = re.compile(r"\b(book|reserve)\b", re.IGNORECASE)
_INVENTORY_DESTINATION_TEXT = re.compile(
    r"\b(my\s*reservations?|my\s*trips?|account\s+(?:reservations?|bookings?|trips?|stays?))\b",
    re.IGNORECASE,
)
_CONFIRMATION_DESTINATION_TEXT = re.compile(
    r"\b(confirmation|reservation\s*details?|booking\s*details?|trip\s*details?)\b",
    re.IGNORECASE,
)
_SAFE_LOG_QUERY_KEY = re.compile(r"^[a-z][a-z0-9_.-]{0,31}$")
_BENIGN_DATA_QUERY_KEYS = frozenset(
    {
        "arrival",
        "check_in",
        "check_out",
        "checkin",
        "checkout",
        "departure",
    }
)
_CONTROL_QUERY_KEY_TEXT = re.compile(
    r"\b(action|command|destination|intent|next|operation|path|redirect|route|target|url)\b",
    re.IGNORECASE,
)
_SAFE_LOG_PATH_COMPONENTS = frozenset(
    {
        "account",
        "auth",
        "booking",
        "bookings",
        "captcha",
        "challenge",
        "confirmation",
        "confirmation.html",
        "detail",
        "details",
        "login",
        "my-reservations",
        "my-trips",
        "myreservations",
        "myreservations.html",
        "mytrips",
        "mytrips.html",
        "reservation",
        "reservations",
        "sign-in",
        "signin",
        "stay",
        "stays",
        "trip",
        "trips",
        "verify-human",
    }
)


class DestinationDisposition(Enum):
    DENY = "deny"
    OBSERVE_ONLY = "observe_only"
    INTERACT = "interact"


class DestinationCategory(Enum):
    INVENTORY = "inventory"
    CONFIRMATION = "confirmation"
    AUTHENTICATION = "authentication"
    CHALLENGE = "challenge"
    MUTATION = "mutation"
    UNKNOWN_BOOKING = "unknown_booking"
    EXTERNAL = "external"
    INVALID = "invalid"


@dataclass(frozen=True, slots=True)
class DestinationAssessment:
    disposition: DestinationDisposition
    category: DestinationCategory
    host_class: str
    path_template: str
    query_keys: tuple[str, ...]
    fragment_present: bool
    terminal_status: InventoryExecutionStatus | None = None


def _assess_destination(url: str | None) -> DestinationAssessment:
    if url is None or len(url) > 2_000:
        return _destination_assessment(DestinationCategory.INVALID)
    try:
        parsed = urlsplit(url)
        pairs = parse_qsl(parsed.query, keep_blank_values=True)
    except (TypeError, ValueError):
        return _destination_assessment(DestinationCategory.INVALID)
    if not is_booking_destination(url):
        return _destination_assessment(
            DestinationCategory.EXTERNAL,
            parsed=parsed,
            pairs=pairs,
        )

    decoded_path = unquote(parsed.path)
    decoded_fragment = unquote(parsed.fragment)
    path_fragment_text = _normalize_destination_text(f"{decoded_path} {decoded_fragment}")
    query_key_text = " ".join(
        _normalize_destination_text(unquote(key))
        for key, _value in pairs
        if unquote(key).casefold() not in _BENIGN_DATA_QUERY_KEYS
    )
    control_query_value_text = " ".join(
        _normalize_destination_text(unquote(value))
        for key, value in pairs
        if _CONTROL_QUERY_KEY_TEXT.search(_normalize_destination_text(unquote(key)))
    )
    risk_text = " ".join(
        part for part in (path_fragment_text, query_key_text, control_query_value_text) if part
    )
    terminal_status = None
    if _CHALLENGE_DESTINATION_TEXT.search(risk_text):
        category = DestinationCategory.CHALLENGE
        terminal_status = (
            InventoryExecutionStatus.CAPTCHA
            if "captcha" in risk_text or "verify human" in risk_text
            else InventoryExecutionStatus.BOT_WALL
        )
    elif _AUTH_DESTINATION_TEXT.search(risk_text):
        category = DestinationCategory.AUTHENTICATION
        terminal_status = (
            InventoryExecutionStatus.MFA_REQUIRED
            if "two factor" in risk_text or "mfa" in risk_text
            else InventoryExecutionStatus.SIGNED_OUT
        )
    elif _MUTATION_DESTINATION_TEXT.search(risk_text) or _MUTATION_PATH_TEXT.search(
        path_fragment_text
    ):
        category = DestinationCategory.MUTATION
    elif _CONFIRMATION_DESTINATION_TEXT.search(path_fragment_text):
        category = DestinationCategory.CONFIRMATION
    elif _INVENTORY_DESTINATION_TEXT.search(path_fragment_text):
        category = DestinationCategory.INVENTORY
    else:
        category = DestinationCategory.UNKNOWN_BOOKING
    return _destination_assessment(
        category,
        parsed=parsed,
        pairs=pairs,
        terminal_status=terminal_status,
    )


def _destination_assessment(
    category: DestinationCategory,
    *,
    parsed: SplitResult | None = None,
    pairs: Sequence[tuple[str, str]] = (),
    terminal_status: InventoryExecutionStatus | None = None,
) -> DestinationAssessment:
    disposition = (
        DestinationDisposition.INTERACT
        if category in {DestinationCategory.INVENTORY, DestinationCategory.CONFIRMATION}
        else DestinationDisposition.OBSERVE_ONLY
        if category is DestinationCategory.UNKNOWN_BOOKING
        else DestinationDisposition.DENY
    )
    path = _sanitized_path_template(parsed.path if parsed is not None else "")
    keys = tuple(
        sorted(
            {
                key.casefold() if _SAFE_LOG_QUERY_KEY.fullmatch(key.casefold()) else "{key}"
                for key, _value in pairs
            }
        )[:16]
    )
    host_class = _host_class(parsed, category)
    return DestinationAssessment(
        disposition,
        category,
        host_class,
        path,
        keys,
        bool(parsed is not None and parsed.fragment),
        terminal_status,
    )


def _normalize_destination_text(value: str) -> str:
    camel_split = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", value)
    return " ".join(re.sub(r"[^a-z0-9]+", " ", camel_split.casefold()).split())


def _host_class(parsed: SplitResult | None, category: DestinationCategory) -> str:
    if parsed is None or not is_booking_destination(parsed.geturl()):
        return category.value
    host = (parsed.hostname or "").casefold().rstrip(".")
    return {
        "secure.booking.com": "secure_booking",
        "account.booking.com": "account_booking",
        "www.booking.com": "www_booking",
    }.get(host, "other_booking")


def _sanitized_path_template(path: str) -> str:
    components = []
    for raw in unquote(path).casefold().split("/"):
        if not raw:
            continue
        components.append(raw if raw in _SAFE_LOG_PATH_COMPONENTS else "{segment}")
        if len(components) == 8:
            break
    return "/" + "/".join(components) if components else "/"


def _navigation_terminal(url: str) -> InventoryExecutionStatus | None:
    return _assess_destination(url).terminal_status


def _enum_value(enum_type: type[Enum], raw: object) -> Any:
    normalized = str(raw).strip().casefold()
    for member in enum_type:
        if str(member.value).casefold() == normalized:
            return member
    raise ValueError(f"unsupported {enum_type.__name__} value")


def _completeness_value(raw: object) -> EvidenceCompleteness:
    """Treat absent/unknown provider evidence as incomplete, never as positive proof."""

    if _optional_extracted_text(raw) is None:
        return EvidenceCompleteness.INCOMPLETE
    if str(raw).strip().casefold() == "unknown":
        return EvidenceCompleteness.INCOMPLETE
    return cast(EvidenceCompleteness, _enum_value(EvidenceCompleteness, raw))


def _tri_state_value(raw: object) -> bool | None:
    if isinstance(raw, bool):
        return raw
    if not isinstance(raw, str):
        return None
    normalized = raw.strip().casefold()
    if normalized == "true":
        return True
    if normalized == "false":
        return False
    if normalized == "unknown":
        return None
    raise ValueError("unsupported tri-state evidence")


def _optional_extracted_text(raw: object, *, maximum: int | None = None) -> str | None:
    """Decode the provider's schema-simple sentinel without trusting it as evidence."""

    if raw is None:
        return None
    value = str(raw).strip()
    if value.casefold() in {"", "unknown", "null", "none", "not_visible"}:
        return None
    if maximum is not None and len(value) > maximum:
        raise ValueError("extracted text exceeds the code-owned bound")
    return value


def _optional_extracted_int(
    raw: object,
    *,
    minimum: int,
    maximum: int,
) -> int | None:
    """Keep unreadable occupancy unknown instead of dropping identity-valid evidence."""

    value = _optional_extracted_text(raw)
    if value is None:
        return None
    try:
        parsed = int(value)
    except ValueError:
        return None
    if parsed < minimum or parsed > maximum:
        return None
    return parsed


def _map_reservation(
    scope: InventoryScope,
    raw: Mapping[str, Any],
) -> ObservedReservation:
    remote_id = _optional_extracted_text(raw.get("remote_id"), maximum=128)
    if remote_id is None:
        raise ValueError("reservation identity is required")
    check_in_value = _optional_extracted_text(raw.get("check_in"))
    check_out_value = _optional_extracted_text(raw.get("check_out"))
    check_in = date.fromisoformat(check_in_value) if check_in_value is not None else None
    check_out = date.fromisoformat(check_out_value) if check_out_value is not None else None
    total = None
    booked_total = _optional_extracted_text(raw.get("booked_total"))
    currency = _optional_extracted_text(raw.get("currency"), maximum=3)
    if booked_total is not None and currency is not None:
        total = Money.of(booked_total, currency)
    occupancy = None
    occupancy_values = (
        _optional_extracted_int(raw.get("adults"), minimum=1, maximum=100),
        _optional_extracted_int(raw.get("children"), minimum=0, maximum=100),
        _optional_extracted_int(raw.get("rooms"), minimum=1, maximum=100),
    )
    if all(value is not None for value in occupancy_values):
        occupancy = Occupancy(
            adults=int(cast(int, occupancy_values[0])),
            children=int(cast(int, occupancy_values[1])),
            rooms=int(cast(int, occupancy_values[2])),
        )
    refundability = _enum_value(RefundabilityEvidence, raw.get("refundability"))
    lifecycle = _optional_extracted_text(raw.get("lifecycle"))
    refund_deadline_value = _optional_extracted_text(raw.get("refund_deadline"))
    return ObservedReservation(
        remote_id=remote_id,
        identity_evidence=_completeness_value(raw.get("identity_evidence")),
        scope=scope,
        lifecycle=(
            _enum_value(ReservationLifecycle, lifecycle) if lifecycle is not None else None
        ),
        confirmation_id=_optional_extracted_text(raw.get("confirmation_id"), maximum=128),
        property_name=_optional_extracted_text(raw.get("property_name"), maximum=500),
        property_reference=_optional_extracted_text(
            raw.get("property_reference"), maximum=500
        ),
        check_in=check_in,
        check_out=check_out,
        room_type=_optional_extracted_text(raw.get("room_type"), maximum=500),
        booked_total=total,
        booked_total_source="jev" if raw.get("booked_total_source") == "jev" else "code",
        all_in=_enum_value(AllInEvidence, raw.get("all_in")),
        refundability=refundability,
        refundability_text=_optional_extracted_text(
            raw.get("refundability_text"), maximum=1_000
        ),
        refund_deadline=(
            date.fromisoformat(refund_deadline_value)
            if refund_deadline_value is not None
            else None
        ),
        occupancy=occupancy,
        completeness=_completeness_value(raw.get("completeness")),
    )

