"""Track observed inventory navigation without granting account-completeness authority."""

from __future__ import annotations

import asyncio
import hashlib
import json
import re
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import parse_qs, parse_qsl, unquote, urlsplit

from .browser_use_runtime import BrowserUseActionGuard

ENTRY_URL = "https://secure.booking.com/mytrips.html"
_MAX_LINKS = 250
_TRIP_TRACKING_KEYS = frozenset({"aid", "label", "sid"})
_DETAIL_TRACKING_KEYS = frozenset({"aid", "label", "source"})


def _query_key(value: str) -> str:
    for _ in range(4):
        decoded = unquote(value)
        if decoded == value:
            break
        value = decoded
    return value.strip().casefold()


def inventory_page_kind(url: str) -> str | None:
    if not BrowserUseActionGuard.observable_url(url):
        return None
    parsed = urlsplit(url)
    if parsed.hostname != "secure.booking.com" or parsed.fragment:
        return None
    query = parse_qs(parsed.query, keep_blank_values=True, max_num_fields=200)
    if any(_query_key(key) in {"tab", "scope", "status"} for key in query):
        return None
    for identity_key in ("trip_id", "auth_key"):
        matching_keys = [key for key in query if _query_key(key) == identity_key]
        if matching_keys and (
            matching_keys != [identity_key]
            or len(query[identity_key]) != 1
            or not query[identity_key][0].strip()
        ):
            return None
    if re.fullmatch(r"/confirmation(?:\.[a-z]{2}(?:-[a-z]{2})?)?\.html", parsed.path):
        return "reservation_detail"
    if parsed.path == "/mytrips.html":
        if "trip_id" in query:
            return "trip"
        if set(query).issubset(_TRIP_TRACKING_KEYS):
            return "root"
    return None


@dataclass(frozen=True, slots=True)
class InventoryPageLinks:
    url: str = field(repr=False)
    urls: tuple[str, ...] = field(repr=False)
    truncated: bool = False


async def read_inventory_page_links(browser_session: Any) -> InventoryPageLinks | None:
    """Read rendered links locally; raw link tokens never enter diagnostic output."""
    try:
        async with asyncio.timeout(5):
            target_id = browser_session.agent_focus_target_id
            if not isinstance(target_id, str) or not target_id:
                return None
            source = await browser_session.get_current_page_url()
            if inventory_page_kind(source) is None:
                return None
            pooled = await browser_session.get_or_create_cdp_session(target_id, focus=False)
            if (
                pooled is None
                or pooled.target_id != target_id
                or browser_session.agent_focus_target_id != target_id
                or len(browser_session.get_page_targets()) != 1
            ):
                return None
            session_id = pooled.session_id
            if not isinstance(session_id, str) or not session_id:
                return None
            result = await asyncio.wait_for(
                pooled.cdp_client.send.Runtime.evaluate(
                    params={
                        "expression": (
                            "JSON.stringify({url:location.href,links:Array.from("
                            "document.querySelectorAll('a[href]')).filter(a=>"
                            "a.getClientRects().length && a.innerText.trim()).slice(0,251)"
                            ".map(a=>a.href)})"
                        ),
                        "returnByValue": True,
                    },
                    session_id=session_id,
                ),
                timeout=5,
            )
            raw = result.get("result", {}).get("value")
            value = json.loads(raw) if isinstance(raw, str) else None
            if not isinstance(value, dict):
                return None
            url, links = value.get("url"), value.get("links")
            if not isinstance(url, str) or inventory_page_kind(url) is None:
                return None
            if not isinstance(links, list) or len(links) > _MAX_LINKS + 1:
                return None
            if any(not isinstance(link, str) or len(link) > 4_000 for link in links):
                return None
            if (
                url != source
                or await browser_session.get_current_page_url() != source
                or browser_session.agent_focus_target_id != target_id
                or len(browser_session.get_page_targets()) != 1
            ):
                return None
            return InventoryPageLinks(url, tuple(links[:_MAX_LINKS]), len(links) > _MAX_LINKS)
    except Exception:
        return None


@dataclass(slots=True)
class InventoryTraversal:
    """Observed-link worklist. Visiting a detail page does not prove its facts were read."""

    _pending: dict[str, str] = field(default_factory=dict, repr=False)
    _visited: set[str] = field(default_factory=set, repr=False)
    _kinds: dict[str, str] = field(default_factory=dict, repr=False)
    _root_seen: bool = False
    _truncated: bool = False
    _unlinked_pages: int = 0

    @staticmethod
    def _key(url: str) -> str:
        parsed = urlsplit(url)
        kind = inventory_page_kind(url)
        query = parse_qsl(parsed.query, keep_blank_values=True, max_num_fields=200)
        path = parsed.path
        ignored_keys: frozenset[str] = frozenset()
        if kind in {"root", "trip"}:
            ignored_keys = _TRIP_TRACKING_KEYS
        elif kind == "reservation_detail" and any(key == "auth_key" for key, _ in query):
            # Only the observed per-reservation auth key qualifies localized/manage aliases.
            # Other unknown query fields retain their identity contribution.
            path = "/confirmation.html"
            ignored_keys = _DETAIL_TRACKING_KEYS
        canonical = json.dumps(
            (
                kind,
                path,
                sorted(
                    (pair for pair in query if pair[0] not in ignored_keys),
                    key=lambda pair: pair[0],
                ),
            ),
            separators=(",", ":"),
        )
        return hashlib.sha256(canonical.encode()).hexdigest()

    def observe(self, page: InventoryPageLinks) -> None:
        kind = inventory_page_kind(page.url)
        if kind is None:
            return
        key = self._key(page.url)
        if kind != "root" and key not in self._kinds:
            # Never infer parent/child membership from an unobserved destination alone.
            self._unlinked_pages += 1
            return
        self._root_seen |= kind == "root"
        self._truncated |= page.truncated
        self._kinds[key] = kind
        self._visited.add(key)
        self._pending.pop(key, None)
        if kind == "reservation_detail":
            return
        for url in page.urls:
            target_kind = inventory_page_kind(url)
            if target_kind not in {"trip", "reservation_detail"}:
                continue
            target_key = self._key(url)
            if len(self._kinds) >= _MAX_LINKS and target_key not in self._kinds:
                self._truncated = True
                continue
            self._kinds[target_key] = target_kind
            if target_key not in self._visited:
                self._pending.setdefault(target_key, url)

    @property
    def next_observed_url(self) -> str | None:
        return next(iter(self._pending.values()), None)

    def diagnostic(self) -> dict[str, int | bool]:
        return {
            "root_seen": self._root_seen,
            "trip_links": sum(kind == "trip" for kind in self._kinds.values()),
            "trips_visited": sum(
                kind == "trip" and key in self._visited for key, kind in self._kinds.items()
            ),
            "detail_links": sum(kind == "reservation_detail" for kind in self._kinds.values()),
            "details_visited": sum(
                kind == "reservation_detail" and key in self._visited
                for key, kind in self._kinds.items()
            ),
            "pending_pages": len(self._pending),
            "truncated": self._truncated,
            "unlinked_page_observations": self._unlinked_pages,
        }
