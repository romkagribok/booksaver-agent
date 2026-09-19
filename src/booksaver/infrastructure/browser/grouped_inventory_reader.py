"""Bounded grouped-trip traversal inside the existing authenticated inventory episode.

Only fresh rendered anchors can be followed. This reader never declares all history complete,
exports a session, changes a remote reservation, or logs page contents.
Separate code-owned Active coverage can authorize local retirement under ADR049.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from urllib.parse import parse_qsl, urlsplit

from .inventory_confirmation_facts import (
    parse_cancelled_confirmation,
    parse_confirmation_facts,
)
from .inventory_link_resolution import (
    ResolvedInventoryLink,
    resolve_rendered_confirmation_view,
    resolve_rendered_inventory_link,
)
from .inventory_traversal import InventoryTraversal, inventory_page_kind

logger = logging.getLogger(__name__)
_ACTIVE_CARD_STATUSES = frozenset({"Confirmed", "Upcoming", "In progress"})
_INACTIVE_CARD_STATUSES = frozenset({"Completed", "Canceled", "Cancelled"})


def _car_booking_link(url: str) -> bool:
    """Recognize the observed car-booking route for counting, never navigation authority."""
    try:
        parsed = urlsplit(url)
        query = parse_qsl(parsed.query, keep_blank_values=True, max_num_fields=2)
        return bool(
            parsed.scheme == "https"
            and parsed.hostname == "cars.booking.com"
            and parsed.username is None
            and parsed.password is None
            and parsed.port is None
            and not parsed.fragment
            and re.fullmatch(r"/my-booking/[0-9]+", parsed.path)
            and (not query or len(query) == 1 and query[0][0] == "preflang")
        )
    except ValueError:
        return False

_READ = """(() => {
 const visible = e => e.isConnected && e.getClientRects().length > 0 &&
   getComputedStyle(e).display !== 'none' && getComputedStyle(e).visibility === 'visible';
 const text = document.body.innerText;
 const anchors = Array.from(document.querySelectorAll('a[href]')).filter(visible);
 const bookingCount = anchor => {
   const counts = new Set(Array.from(anchor.querySelectorAll('*')).filter(visible).map(e =>
     e.textContent.trim().match(/^([1-9][0-9]?)\\s*bookings?$/))
     .filter(Boolean).map(m => Number(m[1])));
   return counts.size === 1 ? Array.from(counts)[0] : null;
 };
 const links = anchors.map(a=>({url:a.href,text:a.innerText.trim(),
                              booking_count:bookingCount(a)}));
 // Bind the property link to its actual DOM position inside this confirmation header.
 // A heading can contain icon markup that splits its text across several text nodes.
 const headings = Array.from(document.querySelectorAll('h1,h2,h3,h4,h5,h6'))
   .filter(visible);
 const exactHeading = label => {
   const matches = headings.filter(e => e.textContent.trim() === label);
   return matches.length === 1 ? matches[0] : null;
 };
 const confirmed = exactHeading('Your stay is confirmed');
 const checkin = exactHeading('Check-in');
 const cancelledHeaders = headings.filter(e =>
   /^Your (?:stay|booking|reservation) (?:is|has been) cancel(?:led|ed)[.!]?$/i
     .test(e.textContent.trim()));
 const cancelledHeader = cancelledHeaders.length === 1 && !confirmed;
 const follows = (left, right) => Boolean(left.compareDocumentPosition(right) &
                                        Node.DOCUMENT_POSITION_FOLLOWING);
 const hotels = confirmed && checkin ? anchors.filter(a=>
   new URL(a.href).pathname.startsWith('/hotel/') && a.innerText.trim() &&
   follows(confirmed, a) && follows(a, checkin))
   .map(a=>({url:a.href,text:a.innerText.trim()})) : [];
 // Only an explicit accessible total proves root exhaustion. Stable links, page bottom,
 // and missing Next controls alone never establish completeness.
 let activeRootTotal = null;
 let activeRootUrls = [];
 const activeTabs = Array.from(document.querySelectorAll('[role="tab"][aria-selected="true"]'))
   .filter(e => visible(e) && e.textContent.trim() === 'Active');
 if (activeTabs.length === 1) {
   const panel = document.getElementById(activeTabs[0].getAttribute('aria-controls') || '');
   const lists = panel ? Array.from(panel.querySelectorAll('[role="list"]')).filter(visible) : [];
   const emptyText = panel ? panel.innerText.replaceAll('’', "'")
     .replace(/\\s+/g, ' ').toLowerCase() : '';
   if (panel && visible(panel) &&
       emptyText.includes("you haven't started any trips yet.") &&
       emptyText.includes("once you make a booking, it'll appear here.") &&
       !panel.querySelector('a[href*="trip_id="],a[href*="confirmation"],' +
         '[aria-busy="true"],[role="progressbar"]') &&
       !Array.from(panel.querySelectorAll('button,a[rel="next"]')).some(e =>
         visible(e) && !e.disabled && e.getAttribute('aria-disabled') !== 'true')) {
     activeRootTotal = 0;
   }
   if (lists.length === 1 && !panel.querySelector('[aria-busy="true"],[role="progressbar"]')) {
     const items = Array.from(lists[0].children).filter(e => e.getAttribute('role') === 'listitem');
     const sizes = items.map(e => Number(e.getAttribute('aria-setsize')));
     const positions = items.map(e => Number(e.getAttribute('aria-posinset'))).sort((a,b)=>a-b);
     const pending = Array.from(panel.querySelectorAll('button,a[rel="next"]')).some(e =>
       visible(e) && !e.disabled && e.getAttribute('aria-disabled') !== 'true');
     if (!pending && items.length === lists[0].children.length &&
         items.length > 0 && items.length <= 25 && items.every(visible) &&
         sizes.every(n => n === items.length) && positions.every((n,i) => n === i+1) &&
         items.every(e => e.querySelectorAll('a[href*="trip_id="]').length === 1)) {
       activeRootTotal = items.length;
       activeRootUrls = items.map(e => e.querySelector('a[href*="trip_id="]').href);
     }
   }
 }
 return JSON.stringify({url:location.href,text:text.slice(0,60001),
   activeRootTotal,activeRootUrls,cancelledHeader,
   links:links.slice(0,251),hotels:hotels.slice(0,11)});
})()"""


@dataclass(frozen=True, slots=True)
class RenderedLink:
    url: str = field(repr=False)
    text: str = field(repr=False)
    booking_count: int | None = field(default=None, repr=False)


@dataclass(frozen=True, slots=True)
class InventorySnapshot:
    url: str = field(repr=False)
    text: str = field(repr=False)
    links: tuple[RenderedLink, ...] = field(repr=False)
    hotel_anchors: tuple[tuple[str, str], ...] = field(repr=False)
    active_root_total: int | None = field(default=None, repr=False)
    cancelled_header: bool = field(default=False, repr=False)
    active_root_urls: tuple[str, ...] = field(default=(), repr=False)


async def read_inventory_snapshot(session: Any) -> InventorySnapshot | None:
    try:
        async with asyncio.timeout(5):
            target = session.agent_focus_target_id
            if not isinstance(target, str) or not target:
                return None
            source = await session.get_current_page_url()
            if (
                inventory_page_kind(source) is None
                or session.agent_focus_target_id != target
                or len(session.get_page_targets()) != 1
            ):
                return None
            pooled = await session.get_or_create_cdp_session(target, focus=False)
            sid = getattr(pooled, "session_id", None)
            if (
                getattr(pooled, "target_id", None) != target
                or not isinstance(sid, str)
                or not sid
                or await session.get_current_page_url() != source
                or session.agent_focus_target_id != target
                or len(session.get_page_targets()) != 1
            ):
                return None
            raw = await pooled.cdp_client.send.Runtime.evaluate(
                params={"expression": _READ, "returnByValue": True},
                session_id=sid,
            )
            encoded = raw.get("result", {}).get("value")
            if not isinstance(encoded, str) or len(encoded) > 1_100_000:
                return None
            value = json.loads(encoded)
            if not isinstance(value, dict) or value.get("url") != source:
                return None
            body, links, hotels = value.get("text"), value.get("links"), value.get("hotels")
            if not isinstance(body, str) or len(body) > 60_000:
                return None
            if not isinstance(links, list) or len(links) > 250:
                return None
            if not isinstance(hotels, list) or len(hotels) > 10:
                return None
            for item in links + hotels:
                if not isinstance(item, dict) or any(
                    not isinstance(item.get(key), str) or len(item[key]) > limit
                    for key, limit in (("url", 4_000), ("text", 8_000))
                ):
                    return None
            if any(item.get("booking_count") is not None and (
                type(item["booking_count"]) is not int or not 1 <= item["booking_count"] <= 99
            ) for item in links):
                return None
            if (
                await session.get_current_page_url() != source
                or session.agent_focus_target_id != target
                or len(session.get_page_targets()) != 1
            ):
                return None
            cancelled_header = value.get("cancelledHeader", False)
            if type(cancelled_header) is not bool:
                return None
            total = value.get("activeRootTotal")
            if total is not None and (type(total) is not int or not 0 <= total <= 25):
                return None
            root_urls = value.get("activeRootUrls", [])
            if (not isinstance(root_urls, list) or len(root_urls) > 25
                or any(not isinstance(url, str) or len(url) > 4_000 for url in root_urls)):
                return None
            return InventorySnapshot(
                source,
                body,
                tuple(RenderedLink(x["url"], x["text"], x.get("booking_count")) for x in links),
                tuple((x["text"], x["url"]) for x in hotels),
                total,
                cancelled_header,
                tuple(root_urls),
            )
    except Exception:
        return None


@dataclass(slots=True)
class GroupedInventoryRead:
    reservations: list[dict[str, str]] = field(default_factory=list, repr=False)
    cancelled_confirmation_ids: set[str] = field(default_factory=set, repr=False)
    active_coverage_complete: bool = False
    root_detail_count: int | None = None
    trip_groups: int = 0
    trips_visited: int = 0
    verified_trip_counts: int = 0
    details_observed: int = 0
    inactive_skipped: int = 0
    nonhotel_skipped: int = 0
    auxiliary_links_skipped: int = 0
    unresolved: int = 0
    desktop_view_used: bool = False

    def diagnostic(self) -> dict[str, int | bool | None]:
        return {
            "root_detail_count": self.root_detail_count,
            "active_coverage_complete": self.active_coverage_complete,
            "trip_groups": self.trip_groups,
            "trips_visited": self.trips_visited,
            "verified_trip_counts": self.verified_trip_counts,
            "details_observed": self.details_observed,
            "inactive_skipped": self.inactive_skipped,
            "cancelled_observed": len(self.cancelled_confirmation_ids),
            "nonhotel_skipped": self.nonhotel_skipped,
            "auxiliary_links_skipped": self.auxiliary_links_skipped,
            "unresolved": self.unresolved,
            "desktop_view_used": self.desktop_view_used,
            "parsed_reservations": len(self.reservations),
        }


class GroupedInventoryReader:
    """One finite worklist; callbacks retain the host's meter, deadline and safety authority."""

    def __init__(
        self,
        session: Any,
        *,
        navigate: Callable[[ResolvedInventoryLink], Awaitable[None]],
        back: Callable[[str], Awaitable[bool]],
        check: Callable[[], Awaitable[None]],
        observed_at: datetime,
        result: GroupedInventoryRead,
    ) -> None:
        self.session = session
        self.navigate = navigate
        self.back = back
        self.check = check
        self.observed_at = observed_at
        self.result = result
        self.last_snapshot: InventorySnapshot | None = None

    async def snapshot(self) -> InventorySnapshot | None:
        await self.check()
        snapshot = await read_inventory_snapshot(self.session)
        await self.check()
        return snapshot

    async def follow(self, target: str, *, desktop: bool = False) -> bool:
        await self.check()
        resolver = (
            resolve_rendered_confirmation_view if desktop else resolve_rendered_inventory_link
        )
        resolved = None
        # A history return can expose the parent shell before its cards finish rendering.
        # Retry only fresh passive resolution, never a stale URL replay or a second episode.
        for attempt in range(3):
            source = await self.session.get_current_page_url()
            resolved = await resolver(
                self.session,
                source_url=source,
                observed_target_url=target,
            )
            await self.check()
            if resolved is not None:
                break
            if attempt < 2:
                await asyncio.sleep(0.4)
        if resolved is None:
            return False
        # Sticky before dispatch: an interrupted navigation may already have set cookies.
        self.result.desktop_view_used |= desktop
        await self.navigate(resolved)
        previous_facts: dict[str, str] | None = None
        for _ in range(20):
            await asyncio.sleep(0.2)
            current = await self.snapshot()
            if (
                current
                and self.same_page(current.url, resolved.target_url)
                and self.ready(current, desktop=desktop)
            ):
                if not desktop:
                    self.last_snapshot = current
                    return True
                # Wait for actual identity/header values, then stable extracted facts.
                # Whole-body equality waits on unrelated menus and promotional content.
                cancelled = self.cancelled_facts(current)
                if cancelled is not None:
                    if cancelled == previous_facts:
                        self.last_snapshot = current
                        return True
                    previous_facts = cancelled
                    continue
                facts = parse_confirmation_facts(
                    current.text, current.hotel_anchors, observed_at=self.observed_at,
                )
                if facts is not None and all(facts.get(key) not in {None, "", "unknown"}
                        for key in ("confirmation_id", "property_name", "property_reference",
                                    "check_in", "check_out")):
                    if facts == previous_facts:
                        self.last_snapshot = current
                        return True
                    previous_facts = facts
                else:
                    previous_facts = None
            else:
                previous_facts = None
        return False

    @staticmethod
    def cancelled_facts(snapshot: InventorySnapshot) -> dict[str, str] | None:
        return parse_cancelled_confirmation(snapshot.text) if snapshot.cancelled_header else None

    @staticmethod
    def ready(snapshot: InventorySnapshot, *, desktop: bool) -> bool:
        if GroupedInventoryReader.cancelled_facts(snapshot) is not None:
            return True
        if len(snapshot.text) <= 100:
            return False
        if inventory_page_kind(snapshot.url) != "reservation_detail":
            return True
        if "Confirmation number" not in snapshot.text:
            return False
        full_details = all(
            label in snapshot.text for label in ("Booking Details", "Your room details", "Price")
        )
        return (
            full_details and len(snapshot.hotel_anchors) == 1
            if desktop
            else (
                full_details
                or any(link.text.strip() == "Desktop version" for link in snapshot.links)
            )
        )

    @staticmethod
    def same_page(left: str, right: str) -> bool:
        return inventory_page_kind(left) is not None and InventoryTraversal._key(
            left
        ) == InventoryTraversal._key(right)

    async def return_to(self, target: str) -> bool:
        for _ in range(4):
            await self.check()
            if not await self.back(target):
                return False
            for _ in range(10):
                await asyncio.sleep(0.2)
                current = await self.snapshot()
                if current and self.same_page(current.url, target) and len(current.text) > 100:
                    return True
        return False

    @staticmethod
    def targets(
        snapshot: InventorySnapshot, kind: str, *, status_only: bool = False,
    ) -> list[RenderedLink]:
        unique: dict[str, RenderedLink] = {}
        for link in snapshot.links:
            if inventory_page_kind(link.url) != kind or not link.text:
                continue
            if status_only and not (
                {line.strip() for line in link.text.splitlines()}
                & (_ACTIVE_CARD_STATUSES | _INACTIVE_CARD_STATUSES)
            ):
                continue
            key = InventoryTraversal._key(link.url)
            # The card carries status; a generic Manage alias carries less evidence.
            prior = unique.get(key)
            if prior is None or (len(prior.text) < len(link.text)):
                unique[key] = link
        return list(unique.values())

    @classmethod
    def reservation_targets(
        cls, snapshot: InventorySnapshot, expected: int | None,
    ) -> list[RenderedLink]:
        links = cls.targets(snapshot, "reservation_detail")
        cards = cls.targets(snapshot, "reservation_detail", status_only=True)
        # A separate management link may carry another token for a listed reservation.
        # Only the observed group's exact booking count plus explicit card statuses can
        # qualify that distinction. Otherwise unknown targets still require inspection.
        if expected is not None and len(cards) + cls.nonhotels(snapshot) == expected:
            return cards
        return links

    @staticmethod
    def nonhotels(snapshot: InventorySnapshot) -> int:
        # Count a rendered confirmed non-hotel card once, never its promotional links.
        return len(
            {
                link.url
                for link in snapshot.links
                if (
                    {line.strip() for line in link.text.splitlines()}.intersection(
                        {"Car rental", "Rental car"}
                    )
                    or _car_booking_link(link.url)
                )
                and "Confirmed" in {line.strip() for line in link.text.splitlines()}
                and inventory_page_kind(link.url) is None
            }
        )

    def unresolved(self, step: str, count: int = 1) -> None:
        self.result.unresolved += count
        # Fixed internal step names only: never log page text, URLs or booking identifiers.
        logger.warning("Grouped inventory incomplete step=%s count=%s", step, count)

    async def run(self) -> bool:
        root = await self.snapshot()
        if root is None or inventory_page_kind(root.url) != "root":
            return False
        self.result.root_detail_count = len(self.targets(root, "reservation_detail"))
        trips = self.targets(root, "trip")
        if not trips:
            if root.active_root_total == 0 and self.result.root_detail_count == 0:
                await asyncio.sleep(0.4)
                final = await self.snapshot()
                self.result.active_coverage_complete = bool(
                    final is not None and final.active_root_total == 0
                    and self.membership(final) == self.membership(root)
                )
                return self.result.active_coverage_complete
            return False
        self.result.trip_groups = len(trips)
        if len(trips) > 25:
            self.unresolved("trip_limit", len(trips))
            return True
        seen: set[str] = set()
        for trip in trips:
            if not await self.follow(trip.url):
                self.unresolved("trip_navigation")
                return True
            expected = re.search(r"(?:^|\n)([1-9][0-9]?) bookings?(?:\n|$)", trip.text)
            expected_count = trip.booking_count
            if expected_count is None and expected is not None:
                expected_count = int(expected[1])
            group = await self.snapshot()
            if expected_count is not None:
                for _ in range(20):
                    if group is not None and len(
                        self.targets(group, "reservation_detail", status_only=True)
                    ) + self.nonhotels(group) == expected_count:
                        break
                    await asyncio.sleep(0.2)
                    group = await self.snapshot()
            if group is None:
                self.unresolved("trip_snapshot")
                return True
            nonhotel_count = self.nonhotels(group)
            count_verified = expected_count is not None and (
                len(self.targets(group, "reservation_detail", status_only=True)) + nonhotel_count
                == expected_count
            )
            if count_verified:
                self.result.verified_trip_counts += 1
            elif expected_count is not None:
                self.unresolved("trip_card_count")
            self.result.trips_visited += 1
            details = self.reservation_targets(group, expected_count)
            self.result.auxiliary_links_skipped += (
                len(self.targets(group, "reservation_detail")) - len(details)
            )
            if not details and not (count_verified and nonhotel_count > 0):
                self.unresolved("empty_trip")
            # Positive non-hotel classifications are counted without opening external links.
            self.result.nonhotel_skipped += nonhotel_count
            for detail in details:
                key = InventoryTraversal._key(detail.url)
                if key in seen:
                    continue
                seen.add(key)
                if len(seen) > 25:
                    self.unresolved("detail_limit")
                    return True
                # Canonical aliases can carry different status labels. A longer inactive label
                # must not hide an active status on another rendered link to the same booking.
                lines = {
                    line.strip()
                    for alias in group.links
                    if inventory_page_kind(alias.url) == "reservation_detail"
                    and InventoryTraversal._key(alias.url) == key
                    for line in alias.text.splitlines()
                }
                card_conflict = bool(
                    lines & _INACTIVE_CARD_STATUSES and lines & _ACTIVE_CARD_STATUSES
                )
                if lines & _INACTIVE_CARD_STATUSES:
                    if not lines & _ACTIVE_CARD_STATUSES:
                        if "Completed" in lines and not lines & {"Canceled", "Cancelled"}:
                            self.result.inactive_skipped += 1
                            continue
                    else:
                        self.unresolved("conflicting_card_status")
                if not await self.follow(detail.url):
                    self.unresolved("detail_navigation")
                    return True
                snapshot = self.last_snapshot
                if snapshot is None:
                    self.unresolved("detail_snapshot")
                    return True
                desktop = [
                    link for link in snapshot.links if link.text.strip() == "Desktop version"
                ]
                if len(desktop) == 1 and self.cancelled_facts(snapshot) is None:
                    if not await self.follow(desktop[0].url, desktop=True):
                        snapshot = None
                    else:
                        snapshot = self.last_snapshot
                self.result.details_observed += 1
                if snapshot is not None:
                    cancelled = self.cancelled_facts(snapshot)
                    cancellation_card = (
                        bool(lines & {"Canceled", "Cancelled"}) and not card_conflict
                    )
                    if cancellation_card and cancelled is None:
                        self.unresolved("cancellation_not_verified")
                    facts = cancelled or parse_confirmation_facts(
                        snapshot.text, snapshot.hotel_anchors, observed_at=self.observed_at
                    )
                    if (cancelled is not None and card_conflict) or (
                        cancellation_card and cancelled is None
                    ):
                        facts = None
                    if cancelled is not None and not card_conflict:
                        self.result.cancelled_confirmation_ids.add(cancelled["confirmation_id"])
                    if facts is not None:
                        self.result.reservations.append(facts)
                    else:
                        self.unresolved("confirmation_facts")
                else:
                    self.unresolved("desktop_details")
                if not await self.return_to(group.url):
                    self.unresolved("trip_return")
                    return True
            final_group = await self.snapshot()
            if final_group is None or self.membership(final_group) != self.membership(group):
                self.unresolved("group_membership_changed")
            if not await self.return_to(root.url):
                self.unresolved("root_return")
                return True
        final_root = await self.snapshot()
        self.result.active_coverage_complete = bool(
            root.active_root_total == len(trips)
            and len(root.active_root_urls) == len(trips)
            and all(inventory_page_kind(url) == "trip" for url in root.active_root_urls)
            and {InventoryTraversal._key(url) for url in root.active_root_urls}
                == {InventoryTraversal._key(trip.url) for trip in trips}
            and final_root is not None
            and final_root.active_root_total == root.active_root_total
            and final_root.active_root_urls == root.active_root_urls
            and self.membership(final_root) == self.membership(root)
            and self.result.root_detail_count == 0
            and self.result.verified_trip_counts == len(trips)
            and self.result.trips_visited == len(trips)
            and self.result.unresolved == 0
            and self.result.details_observed == len(self.result.reservations)
            and all(raw.get("lifecycle") in {"upcoming", "current", "completed", "cancelled"}
                    and raw.get("confirmation_id") for raw in self.result.reservations)
            and len({raw["confirmation_id"] for raw in self.result.reservations})
                == len(self.result.reservations)
        )
        return True

    @staticmethod
    def membership(snapshot: InventorySnapshot) -> frozenset[tuple[str, str, int | None]]:
        return frozenset(
            (InventoryTraversal._key(link.url), link.text, link.booking_count)
            for link in snapshot.links
            if inventory_page_kind(link.url) in {"trip", "reservation_detail"}
            or _car_booking_link(link.url)
        )
