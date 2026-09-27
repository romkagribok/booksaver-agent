"""Code-owned, read-only page observation for the Jev price method.

The script below is a fixed BookSaver constant evaluated in the page; no model ever supplies
JavaScript.  It segments rendered room/rate cards into bounded text lines so Jev can answer
narrow choice questions, while BookSaver code parses every amount and date itself.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

MAX_ROOMS = 15
MAX_RATES_PER_ROOM = 4
MAX_LINES = 30
MAX_LINE_CHARS = 200

_SNAPSHOT_TEMPLATE = r"""
(() => {
  if (!document.body) return null;
  const MAX_ROOMS = __MAX_ROOMS__, MAX_RATES = __MAX_RATES__, MAX_LINES = __MAX_LINES__,
        MAX_CHARS = __MAX_CHARS__;
  const hidden = '[aria-hidden="true"],[inert],script,style,noscript,template';
  // Struck-through (old) prices are never offered to Jev as candidate totals.
  const struck = e => !!e.closest('s,del,strike') ||
    getComputedStyle(e).textDecorationLine.includes('line-through');
  const rendered = e => !!e && !e.closest(hidden) && !struck(e) &&
    (typeof e.checkVisibility !== 'function' ||
     e.checkVisibility({checkOpacity: true, checkVisibilityCSS: true}));
  const PRICE = /(?:US\$|CA\$|C\$|A\$|AU\$|NZ\$|HK\$|S\$|MX\$|R\$|€|£|¥|₹|\$|\b[A-Z]{3}\s?)\s?\d/;
  const linesOf = (root, skip) => {
    const out = [];
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
    let node;
    while ((node = walker.nextNode()) && out.length < MAX_LINES) {
      const parent = node.parentElement;
      if (!parent || !rendered(parent)) continue;
      if (skip && skip.some(s => s.contains(parent))) continue;
      const value = node.textContent.replace(/\s+/g, ' ').trim();
      if (!value || value === '•') continue;
      const line = value.slice(0, MAX_CHARS);
      if (out.length && out[out.length - 1] === line) continue;
      out.push(line);
    }
    return out;
  };
  let rateCards = [...document.querySelectorAll('[data-testid="rate-card"]')].filter(rendered);
  if (!rateCards.length) {
    // Generic fallback: the innermost card-like ancestor of each rendered price text.
    const seen = new Set();
    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
    let node;
    while ((node = walker.nextNode()) && seen.size < MAX_ROOMS * MAX_RATES) {
      const parent = node.parentElement;
      if (!parent || !PRICE.test(node.textContent) || !rendered(parent)) continue;
      const card = parent.closest('label,[role="radio"],[role="row"],tr,li,article');
      if (card && (card.innerText || '').length <= 1500) seen.add(card);
    }
    rateCards = [...seen].filter(c => ![...seen].some(o => o !== c && c.contains(o)));
  }
  const rooms = [];
  const roomIndex = new Map();
  for (const rate of rateCards) {
    // Without an explicit room card, never guess a wider container: it could span several
    // room types and credit one room's rate to another. The rate card then names its own room.
    const room = rate.closest('[data-testid="room-card"]') || rate;
    if (!roomIndex.has(room)) {
      if (rooms.length >= MAX_ROOMS) continue;
      roomIndex.set(room, {element: room, rates: []});
      rooms.push(roomIndex.get(room));
    }
    const entry = roomIndex.get(room);
    if (entry.rates.length < MAX_RATES && rate !== room) entry.rates.push(rate);
    else if (rate === room && !entry.rates.length) entry.rates.push(rate);
  }
  const headings = [];
  const headingSelector = 'h1,h2,[data-testid*="title" i],[class*="hotel-name" i]';
  for (const e of document.querySelectorAll(headingSelector)) {
    if (!rendered(e)) continue;
    const text = (e.innerText || '').replace(/\s+/g, ' ').trim();
    if (text && text.length <= MAX_CHARS && !headings.includes(text)) headings.push(text);
    if (headings.length >= 12) break;
  }
  const viewportLines = [];
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  const range = document.createRange();
  let node, length = 0;
  while ((node = walker.nextNode()) && length < 4000) {
    const value = node.textContent.replace(/\s+/g, ' ').trim();
    const parent = node.parentElement;
    if (!value || !parent || !rendered(parent)) continue;
    range.selectNodeContents(node);
    const r = range.getBoundingClientRect();
    if (r.width > 0 && r.height > 0 && r.bottom > 0 && r.top < innerHeight) {
      viewportLines.push(value.slice(0, MAX_CHARS));
      length += value.length;
    }
  }
  return {
    url: location.href,
    title: document.title.slice(0, MAX_CHARS),
    headings,
    viewport_text: viewportLines.join('\n').slice(0, 4000),
    rooms: rooms.map(room => ({
      lines: room.rates.length && room.rates[0] !== room.element
        ? linesOf(room.element, room.rates) : [],
      rates: room.rates.map(rate => linesOf(rate, null)),
    })),
  };
})()
"""
OFFER_SNAPSHOT_JS = (
    _SNAPSHOT_TEMPLATE.replace("__MAX_ROOMS__", str(MAX_ROOMS))
    .replace("__MAX_RATES__", str(MAX_RATES_PER_ROOM))
    .replace("__MAX_LINES__", str(MAX_LINES))
    .replace("__MAX_CHARS__", str(MAX_LINE_CHARS))
)


@dataclass(frozen=True, slots=True)
class RoomSnapshot:
    lines: tuple[str, ...]
    rates: tuple[tuple[str, ...], ...]


@dataclass(frozen=True, slots=True)
class OfferPageSnapshot:
    url: str
    title: str
    headings: tuple[str, ...]
    viewport_text: str
    rooms: tuple[RoomSnapshot, ...]

    @property
    def rate_count(self) -> int:
        return sum(len(room.rates) for room in self.rooms)


def _bounded_lines(raw: object, *, limit: int = MAX_LINES) -> tuple[str, ...]:
    if not isinstance(raw, list):
        return ()
    lines: list[str] = []
    for item in raw[:limit]:
        if isinstance(item, str):
            value = " ".join(item.split())[:MAX_LINE_CHARS]
            if value:
                lines.append(value)
    return tuple(lines)


def parse_offer_snapshot(raw: Any) -> OfferPageSnapshot | None:
    """Validate the page-provided structure; page content stays untrusted text."""

    if not isinstance(raw, dict):
        return None
    url = raw.get("url")
    if not isinstance(url, str) or not 1 <= len(url) <= 4_000:
        return None
    rooms: list[RoomSnapshot] = []
    raw_rooms = raw.get("rooms")
    if isinstance(raw_rooms, list):
        for raw_room in raw_rooms[:MAX_ROOMS]:
            if not isinstance(raw_room, dict):
                continue
            raw_rates = raw_room.get("rates")
            bounded_rates = raw_rates[:MAX_RATES_PER_ROOM] if isinstance(raw_rates, list) else []
            rates = tuple(lines for lines in map(_bounded_lines, bounded_rates) if lines)
            if rates:
                rooms.append(RoomSnapshot(_bounded_lines(raw_room.get("lines")), rates))
    title = raw.get("title")
    viewport_text = raw.get("viewport_text")
    return OfferPageSnapshot(
        url=url,
        title=title[:MAX_LINE_CHARS] if isinstance(title, str) else "",
        headings=_bounded_lines(raw.get("headings"), limit=12),
        viewport_text=viewport_text[:4_000] if isinstance(viewport_text, str) else "",
        rooms=tuple(rooms),
    )
