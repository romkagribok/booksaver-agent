---
intent: 035-jev-judges-price-offers
phase: construction
status: construction
created: "2026-11-10T00:36:30Z"
updated: "2026-11-10T00:36:30Z"
---

# Requirements: Jev judges the room, hotel, meals, refund and taxes of price offers

## Intent overview

Release B of the owner's plan "Jev reads every fact" (A: sync facts, deployed 21694ab; C: discovery).
Production on 2026-11-09 shows two of the owner's father's bookings never priced because the room
name on the hotel page differs from the name on the confirmation: AIRINN "Standard Double Room" vs
"Double Room" (15+ failed checks) and Park Plaza "Deluxe Queen Bed" vs a "Deluxe Queen Room" offer.
The audit also found English word lists that overrule Jev's rate answers (meals, refund, taxes) and an
exact hotel-name comparison even when the Booking.com link already proves the hotel.

## Functional requirements

- **FR-1.** When no priced room carries the booked room name, Jev is shown the booked room and every
  priced room on the page and names the one that is the same room type, or none. Asked twice; both
  answers must agree at 0.8 or more. Offers of that room count as the booked room. An exact name match
  needs no question.
- **FR-2.** A page whose Booking.com hotel link matches the booking is the booked hotel; the visible
  name is still required but need not equal the saved one. Bookings saved with only a name keep the
  exact-name rule.
- **FR-3.** Jev classifies each rate's meals (none, breakfast, half board, full board, all inclusive)
  and names the line stating them. An included plan counts only with a named line and confidence 0.8;
  anything else is unknown, which can only exclude an offer. The code meal word lists are removed.
- **FR-4.** Jev's refund class and tax answer count when it names the line stating them, at
  confidence 0.8. The English refund and tax patterns that vetoed Jev are removed.
- **FR-6.** (Owner, 2026-11-10: "yes it should count as a saving (same or better)".) A cheaper
  offer for a room Jev judges the same as or better than the booked room counts. Jev compares every
  priced room without the booked name with the booked room for the booked guests (same, better,
  neither), asked twice, agreement at 0.8. The alert names the offered room and says whether it is
  the same room type named differently or a better room.
- **FR-5.** The whole-stay total keeps its code check (money-critical; every rate was priced in
  production on 2026-11-08/09; a failure is loud, not wrong).

## Out of scope

Stay facts from URL parameters, child ages in price checks, the daily per-user check limit, discovery
(release C).
