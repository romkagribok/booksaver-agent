---
stage: implement
bolt: 104-jev-reads-room-type
created: 2026-11-08T02:39:22Z
---

# Implementation Walkthrough

- `JevReservationFacts`: when the code facts show one room, the same two calls also ask a `room`
  choice over the page's unique lines of at most 120 characters (first 120); both calls must agree at
  0.5 or more. The question names "Your room details" and says a general unit category such as
  "Private suite" comes first; a wording that excluded "bed details" made Jev reject "Deluxe Queen
  Bed", and a wording without the hint picked "Private suite".
- The booked total needs agreement and `check_total`, no confidence floor.
- `parse_confirmation_facts`: `_room_fact` deleted; meals are read for any single-room party.
- Price checks: "No matching room type found: N prices found; room_mismatch=N." when every exclusion
  is the room, otherwise "No equivalent offer found: ...".

Codex review (PR #106, P1): the room options were every short page line, so guest names, the
confirmation number, PIN and email reached TypeSafe. `room_candidates` now takes only the lines under
"Your room details" before the guest row (at most 8), drops any line with an email, a long number or a
PIN, and those lines are the room question's state. Without the section in the state Jev answered
"none"; with it, 0.97 to 1.0.
