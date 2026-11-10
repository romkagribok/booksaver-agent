---
id: 001-jev-judges-room-and-rate-terms
unit: 001-jev-judges-room-and-rate-terms
intent: 035-jev-judges-price-offers
status: complete
priority: must
created: "2026-11-10T00:36:30Z"
assigned_bolt: 106-jev-judges-room-and-rate-terms
implemented: true
---

# US-258: Jev judges the booked room and each rate's terms

## User story

As a BookSaver user, I want my booking priced even when the hotel names my room differently, with
meals, refund and taxes judged by Jev rather than fixed English phrases, so that price checks keep
working without code changes.

## Assigned requirement

FR-1 to FR-5.

## Acceptance criteria

- [x] Given no priced room with the booked name and two agreeing answers at 0.8 naming one, when checked, then its offers count as the booked room.
- [x] Given disagreement, low confidence or "none", when checked, then no offer counts as the booked room.
- [x] Given an exact name match, when checked, then no room question is asked.
- [x] Given a matching Booking.com link and a different visible name, when checked, then the page is the booked hotel; a name-only booking still needs the exact name.
- [x] Given a rate Jev classifies as breakfast with a named line at 0.8, when checked, then the offer includes breakfast; without the line it is unknown.
- [x] Given Jev's refund and tax answers with named lines at 0.8, when checked, then they count without English patterns.
- [x] Given the real AIRINN and Park Plaza pages on staging, when checked, then each is priced.

## Out of scope

Totals, URL stay facts, child ages, discovery.
