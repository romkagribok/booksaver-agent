---
intent: 033-jev-reads-room-type
phase: construction
status: construction
created: "2026-11-08T02:21:32Z"
updated: "2026-11-08T02:21:32Z"
---

# Requirements: Jev reads the booked room type; agreed totals are not dropped

## Intent overview

The owner's dad's new Park Plaza Lodge reservation (2026-11-15 to 11-17) showed "Can't check prices:
room type unavailable, booked total unavailable" in /bookings. A replay on cloned data (kit
`parkplaza-20261107`) showed: (1) the room section read "Your room details / Private suite / Deluxe
Queen Bed" and the layout-specific room parser only knew "Entire apartment" as a category line, so it
found no room and, because the meal reader was gated on it, no meal plan either; (2) both Jev calls
chose the correct total line "US$344.50" (room rows were in the display currency EUR) at confidence
0.51 and 0.54, below the 0.6 floor, so the agreed and code-checked total was discarded.

## Functional requirements

- **FR-1.** Jev reads the booked room type for single-room reservations in the same two calls that
  read the total and refund terms; both calls must choose the same page line at confidence 0.5 or
  more. The layout-specific room parser is removed.
- **FR-2.** The booked total is accepted when both Jev calls choose the same line and the code check
  (largest amount in its currency in the price area) passes; there is no confidence floor.
- **FR-3.** The booked meal plan is read whenever the page describes a single-room party, no longer
  only when the removed room parser succeeded.
- **FR-4.** A price check that found prices but no offer for the booked room says "No matching room
  type found" instead of "could not verify".
- **FR-5.** Existing tracked reservations keep their room type unless the page shows a different one.

## Out of scope

Jev deciding room equivalence in price checks (AIRINN "Double Room" vs "Standard Double Room"); the
remaining layout-specific readers listed in the audit.
