---
id: 001-jev-classifies-trip-cards
unit: 001-jev-classifies-trip-cards
intent: 037-jev-classifies-trip-cards
status: draft
priority: must
created: "2026-11-10T02:08:13Z"
assigned_bolt: 110-jev-classifies-trip-cards
implemented: false
---

# US-262: Jev classifies trip cards

## User story

As a BookSaver user, I want every hotel in my trips found whatever words Booking.com uses on trip
cards, and trips with flights or attractions synced, so that no booking is silently left unmonitored.

## Assigned requirement

FR-1 to FR-5.

## Acceptance criteria

- [ ] Given agreed classes for every card, when the count equals active stays plus other bookings, then the trip count is verified.
- [ ] Given a renamed status word, when Jev classifies the cards, then an active hotel is still opened and counted.
- [ ] Given a flight or attraction card, when classified as another booking, then the trip count can be verified.
- [ ] Given a card Jev surely calls a completed stay, when synced, then it is skipped; an unclassified card is opened.
- [ ] Given a card Jev calls cancelled, when its page does not verify cancellation, then the sync stays incomplete.
- [ ] Given TypeSafe unavailable, when synced, then the code classification is used.
- [ ] Given the real trip pages on staging, when synced, then every reservation and count is unchanged.

## Out of scope

Loud-only page gates, reservation facts, price checks.
