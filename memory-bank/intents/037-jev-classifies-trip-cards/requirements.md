---
intent: 037-jev-classifies-trip-cards
phase: construction
status: complete
created: "2026-11-10T02:08:13Z"
updated: "2026-11-10T02:08:13Z"
---

# Requirements: Jev classifies trip cards during discovery

## Intent overview

Release C of the owner's plan "Jev reads every fact" (A: sync facts; B: price checks, both deployed).
An audit of the discovery path (2026-11-10) found about 20 fixed-text gates. Most fail loudly (sync
incomplete, stall notice), but trip cards are classified by exact English status words ("Confirmed",
"Completed", "Canceled") and car-rental words: a renamed status can make a trip's count match with an
active hotel left out (silent), a "Completed" card is skipped unopened, and flights or attractions are
never recognised, so any trip containing them is permanently incomplete. Trip pages captured from
production on 2026-11-10 (kit `tripcards-20261110`) show hotel cards, car rentals on
cars.booking.com, a cancelled duplicate, "Manage your booking" aliases and promotional links.

## Functional requirements

- **FR-1.** On each trip page, Jev classifies every booking-like card (reservation links merged per
  booking; other multi-line links) as an active, completed or cancelled stay, an active or inactive
  other booking (car, flight, attraction, transfer), or not a booking. Asked twice; both answers must
  agree at 0.8, otherwise the card is unclassified.
- **FR-2.** The trip's booking count is verified only when every card is classified and the count
  equals active stays plus active other bookings (with or without cancelled stays, as today).
- **FR-3.** A stay card is skipped unopened only when Jev surely calls it completed; a card Jev calls
  cancelled must still be verified on its page; unclassified cards are opened.
- **FR-4.** Card text sent to TypeSafe has personal lines removed, as for confirmation pages.
- **FR-5.** When TypeSafe is unavailable or over budget, the existing code classification is used,
  so a sync still completes during an outage.

## Out of scope

Loud-only gates (page-ready labels, the "Your stay is confirmed" heading, empty-account copy, the
"N bookings" text, Active-tab structure, URL routes) — a later release; reservation facts and price
checks (releases A and B).
