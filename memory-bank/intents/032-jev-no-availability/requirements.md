---
intent: 032-jev-no-availability
phase: construction
status: complete
created: "2026-11-06T16:53:03Z"
updated: "2026-11-06T16:53:03Z"
---

# Requirements: "No availability for your dates" is a conclusive result

## Intent overview

The owner's dad's Kalipè apartment (2027-01-27 to 02-01) failed every Jev price check with
`execution_not_observed`. A replay on cloned data (kit `releaseb2-20261106`, `rooms.log`) showed the
property page lists no rooms for those dates, only 15 suggestions for other dates ("Feb 1 - Feb 3,
2 nights, From EUR 186"); Jev correctly named no room type. BookSaver recorded a technical failure,
so the reservation looked broken and could trigger the stall message.

## Functional requirements

- **FR-1.** When Jev names no room type on the property page, Jev is asked once whether the page
  lists rooms bookable for exactly the requested dates. A confident answer (at least 0.8) that it
  shows only other dates, sold out or no availability ends the check as unavailable, recorded as
  the existing conclusive "no equivalent offer".
- **FR-2.** Any other answer keeps today's result (no valid observation). No layout-specific code.
- **FR-3.** Only the room card lines and the requested dates are sent; the extra call counts toward
  the Jev cap like every other call.

## Out of scope

AIRINN's missing "Standard Double Room" (correctly no equivalent offer).
