"""Bind one explicitly exhausted Active page cache to its rendered trip cards.

This grants no authority by itself: the caller still verifies selected DOM provenance,
stable pre/post membership, every group's contents, authentication, and action guards.
"""

from __future__ import annotations

import json
import re
from urllib.parse import parse_qsl, urlsplit

from .inventory_traversal import inventory_page_kind

_MAX_TRIPS = 25
_MAX_STORE_RECORDS = 101


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate object member")
        result[key] = value
    return result


def _first_active_page(key: str) -> int | None:
    if len(key) > 4_000 or not key.startswith("getTrips(") or not key.endswith(")"):
        return None
    args = json.loads(key[9:-1], object_pairs_hook=_unique_object)
    if not isinstance(args, dict) or set(args) != {"input"}:
        return None
    value = args["input"]
    if not isinstance(value, dict) or not {"stages", "pagination"} <= set(value):
        return None
    if not set(value) <= {"stages", "pagination", "headerSize"}:
        return None
    stages = value["stages"]
    if (not isinstance(stages, list) or len(stages) != 2
        or any(not isinstance(stage, str) for stage in stages)
        or set(stages) != {"CURRENT", "UPCOMING"}):
        return None
    pagination = value["pagination"]
    if (not isinstance(pagination, dict)
        or set(pagination) != {"paginationToken", "rowsPerPage"}
        or pagination["paginationToken"] is not None):
        return None
    rows = pagination["rowsPerPage"]
    if type(rows) is not int or rows != 10:
        return None
    if "headerSize" in value:
        sizes = value["headerSize"]
        if (not isinstance(sizes, list) or len(sizes) != 1
            or not isinstance(sizes[0], dict) or set(sizes[0]) != {"height", "width"}
            or any(type(n) is not int or not 1 <= n <= 10_000 for n in sizes[0].values())):
            return None
    return rows


def verified_active_trip_urls(evidence: object) -> tuple[str, ...] | None:
    """Return bounded original URLs only when cache and rendered identities agree.

    Empty tuples require separate rendered-empty evidence at the caller. Malformed,
    ambiguous, partial, or unsupported cache shapes return None without logging data.
    """
    try:
        return _verified_active_trip_urls(evidence)
    except (ValueError, TypeError, KeyError, RecursionError, OverflowError):
        return None


def _verified_active_trip_urls(evidence: object) -> tuple[str, ...] | None:
    if not isinstance(evidence, dict) or evidence.get("selected_active") is not True:
        return None
    store, links = evidence.get("store"), evidence.get("links")
    if (not isinstance(store, dict) or not 1 <= len(store) <= _MAX_STORE_RECORDS
        or not isinstance(links, list) or len(links) > _MAX_TRIPS):
        return None
    root = store.get("ROOT_QUERY")
    if not isinstance(root, dict) or root.get("__typename") != "Query":
        return None
    queries = root.get("tripsQueries")
    if not isinstance(queries, dict) or queries.get("__typename") != "TripsQueries":
        return None
    keys = [key for key in queries if key != "__typename"]
    if len(keys) != 1 or not isinstance(keys[0], str):
        return None
    rows = _first_active_page(keys[0])
    page = queries[keys[0]]
    if rows is None or not isinstance(page, dict) or set(page) != {
        "__typename", "trips", "backfillStatus", "nextPageData",
    } or page["__typename"] != "GetTripsList" or page["backfillStatus"] is not None:
        return None
    if page["nextPageData"] != {"__typename": "PaginationData", "paginationToken": None}:
        return None
    refs = page["trips"]
    if not isinstance(refs, list) or len(refs) > rows or len(refs) != len(links):
        return None
    counts: dict[str, int] = {}
    for ref in refs:
        if not isinstance(ref, dict) or set(ref) != {"__ref"}:
            return None
        name = ref["__ref"]
        if not isinstance(name, str) or not re.fullmatch(r"Trip:[0-9]{1,30}", name):
            return None
        identity = name[5:]
        trip = store.get(name)
        if (identity in counts or not isinstance(trip, dict)
            or trip.get("__typename") != "Trip" or trip.get("id") != identity
            or trip.get("canceled") is not False):
            return None
        total = trip.get("numberOfReservations")
        active = trip.get("numberOfNonCancelledReservations")
        if type(total) is not int or type(active) is not int or not 1 <= active <= total <= 99:
            return None
        counts[identity] = active
    urls: list[str] = []
    seen: set[str] = set()
    for link in links:
        if not isinstance(link, dict) or set(link) != {"url", "booking_count"}:
            return None
        url, count = link["url"], link["booking_count"]
        if not isinstance(url, str) or not 1 <= len(url) <= 4_000:
            return None
        if inventory_page_kind(url) != "trip":
            return None
        parsed = urlsplit(url)
        pairs = parse_qsl(parsed.query, keep_blank_values=True, max_num_fields=20)
        if (parsed.scheme != "https" or parsed.username or parsed.password or parsed.port
            or any(key not in {"trip_id", "aid", "label", "sid"} for key, _ in pairs)
            or len({key for key, _ in pairs}) != len(pairs)):
            return None
        linked_identity = dict(pairs).get("trip_id")
        if (linked_identity is None or linked_identity not in counts or linked_identity in seen
            or type(count) is not int or count != counts[linked_identity]):
            return None
        seen.add(linked_identity)
        urls.append(url)
    return tuple(urls) if seen == set(counts) else None
