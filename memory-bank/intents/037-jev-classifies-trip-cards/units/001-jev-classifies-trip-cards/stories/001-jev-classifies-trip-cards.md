---
id: 001-jev-classifies-trip-cards
unit: 001-jev-classifies-trip-cards
intent: 037-jev-classifies-trip-cards
status: complete
priority: must
created: "2026-11-10T02:08:13Z"
assigned_bolt: 110-jev-classifies-trip-cards
implemented: true
---

# US-262: Jev classifies trip cards

## User story

As a BookSaver user, I want every hotel in my trips found whatever words Booking.com uses on trip
cards, and trips with flights or attractions synced, so that no booking is silently left unmonitored.

## Assigned requirement

FR-1 to FR-5.

## Acceptance criteria

- [x] Given agreed classes for every card, when the count equals active stays plus other bookings, then the trip count is verified.
- [x] Given a renamed status word, when Jev classifies the cards, then an active hotel is still opened and counted.
- [x] Given a flight or attraction card, when classified as another booking, then the trip count can be verified.
- [x] Given a card Jev surely calls a completed stay, when synced, then it is skipped; an unclassified card is opened.
- [x] Given a card Jev calls cancelled, when its page does not verify cancellation, then the sync stays incomplete.
- [x] Given TypeSafe unavailable, when synced, then the code classification is used.
- [x] Given the real trip pages on staging, when synced, then every reservation and count is unchanged.

## Out of scope

Loud-only page gates, reservation facts, price checks.
