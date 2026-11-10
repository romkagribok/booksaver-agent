---
id: 002-same-or-better-room
unit: 001-jev-judges-room-and-rate-terms
intent: 035-jev-judges-price-offers
status: complete
priority: must
created: "2026-11-10T01:15:25Z"
assigned_bolt: 109-same-or-better-room
implemented: true
---

# US-261: A cheaper same-or-better room counts as a saving

## User story

As a BookSaver user, I want to hear about a cheaper refundable offer for a room that is the same as or
better than mine, even when my exact room type is no longer sold, and to see which room it is.

## Assigned requirement

FR-6.

## Acceptance criteria

- [x] Given two agreeing answers at 0.8 that a priced room is better for the booked guests, when checked, then its offers are compared.
- [x] Given "neither", disagreement or low confidence, when checked, then the room is not compared.
- [x] Given rooms that all carry the booked name, when checked, then no comparison question is asked.
- [x] Given a chosen offer for a differently named room, when alerted, then the alert names it and says whether it is the same room type or a better room.
- [x] Given the real AIRINN page on staging, when checked, then Jev's comparison of each room is logged and a better cheaper room, if any, is priced.

## Out of scope

Meal plan and refund rules (unchanged), totals.
