"""Trusted price entry URLs and typed price-observation mapping for the Jev executor."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import InvalidOperation
from enum import Enum
from typing import Any, TypeVar
from urllib.parse import urlencode, urlsplit, urlunsplit

from booksaver.domain.browser_executor import (
    AllInEvidence,
    EvidenceCompleteness,
    ObservedOffer,
    ObservedQueryFacts,
    PriceExecutionRequest,
    RefundabilityEvidence,
)
from booksaver.domain.browser_guard import ExecutorEgressKind, classify_executor_egress
from booksaver.domain.value_objects import Money, Occupancy
from booksaver.infrastructure.browser.browser_use_runtime import BrowserUseActionGuard


@dataclass(frozen=True, slots=True)
class TypedObservation:
    facts: ObservedQueryFacts
    offers: tuple[ObservedOffer, ...]
    evidence_item_count: int


TEnum = TypeVar("TEnum", bound=Enum)


def _enum_value(enum_type: type[TEnum], raw: object) -> TEnum:
    normalized = str(raw).strip().casefold()
    for member in enum_type:
        if str(member.value).casefold() == normalized:
            return member
    raise ValueError(f"unsupported {enum_type.__name__} value")


def _map_extracted_observation(raw: Mapping[str, Any]) -> TypedObservation:
    try:
        from datetime import date

        facts = ObservedQueryFacts(
            property_name=str(raw["property_name"]),
            property_reference=str(raw["property_reference"]),
            check_in=date.fromisoformat(str(raw["check_in"])),
            check_out=date.fromisoformat(str(raw["check_out"])),
            occupancy=Occupancy(
                adults=int(raw["adults"]),
                children=int(raw["children"]),
                rooms=int(raw["rooms"]),
            ),
            currency=str(raw["currency"]),
            authenticated=raw["authenticated"] if isinstance(raw["authenticated"], bool) else None,
            genius=raw["genius"] if isinstance(raw["genius"], bool) else None,
            completeness=_enum_value(EvidenceCompleteness, raw["completeness"]),
        )
        raw_offers = raw["offers"]
        if not isinstance(raw_offers, Sequence) or isinstance(raw_offers, (str, bytes)):
            raise ValueError("offers must be a list")
        offers: list[ObservedOffer] = []
        for item in raw_offers:
            if not isinstance(item, Mapping):
                raise ValueError("offer must be an object")
            offers.append(
                ObservedOffer(
                    room_label=str(item["room_label"]),
                    total=Money.of(str(item["total"]), str(item["currency"])),
                    all_in=_enum_value(AllInEvidence, item["all_in"]),
                    refundability=_enum_value(RefundabilityEvidence, item["refundability"]),
                    refundability_text=(
                        str(item["refundability_text"])
                        if item.get("refundability_text") is not None
                        else None
                    ),
                    completeness=_enum_value(EvidenceCompleteness, item["completeness"]),
                    meal_text=(
                        str(item["meal_text"]) if item.get("meal_text") is not None else None
                    ),
                    booked_room=item.get("booked_room") is True,
                )
            )
    except (KeyError, TypeError, ValueError, InvalidOperation) as exc:
        raise ValueError("typed price observation is invalid") from exc
    return TypedObservation(
        facts=facts,
        offers=tuple(offers),
        evidence_item_count=9 + len(offers) * 6,
    )


def build_trusted_search_url(request: PriceExecutionRequest) -> str:
    query = request.query
    params = {
        "ss": query.property_name,
        "checkin": query.stay_dates.check_in.isoformat(),
        "checkout": query.stay_dates.check_out.isoformat(),
        "group_adults": str(query.occupancy.adults),
        "group_children": str(query.occupancy.children),
        "no_rooms": str(query.occupancy.rooms),
        "selected_currency": query.currency,
        "sb": "1",
        "src": "searchresults",
    }
    url = f"https://www.booking.com/searchresults.html?{urlencode(params)}"
    if classify_executor_egress(url) is not ExecutorEgressKind.BOOKING:
        raise RuntimeError("trusted search destination is outside the executor allowlist")
    return url


def _price_entry_url(request: PriceExecutionRequest) -> tuple[str, str]:
    """Prefer a trusted canonical property page; retain name-only search compatibility."""

    parsed = urlsplit(request.query.property_reference.strip())
    if parsed.scheme.casefold() == "https" and parsed.hostname:
        params = {
            "checkin": request.query.stay_dates.check_in.isoformat(),
            "checkout": request.query.stay_dates.check_out.isoformat(),
            "group_adults": str(request.query.occupancy.adults),
            "group_children": str(request.query.occupancy.children),
            "no_rooms": str(request.query.occupancy.rooms),
            "selected_currency": request.query.currency,
        }
        candidate = urlunsplit(
            (
                "https",
                parsed.netloc,
                parsed.path,
                urlencode(params),
                "",
            )
        )
        if BrowserUseActionGuard.observable_url(candidate):
            return candidate, "property"
    return build_trusted_search_url(request), "search"
