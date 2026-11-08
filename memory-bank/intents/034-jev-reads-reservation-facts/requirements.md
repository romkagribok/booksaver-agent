---
intent: 034-jev-reads-reservation-facts
phase: construction
status: construction
created: "2026-11-08T18:31:21Z"
updated: "2026-11-08T18:31:21Z"
---

# Requirements: Jev reads the booked party, meals and (when needed) dates

## Intent overview

Release A of the owner's plan "Jev reads every fact" (B: price checks; C: discovery). An audit of the
sync reader found: the booked party is read from one closed phrase ("N adults - N nights, 1 room"),
so children or reworded lines leave a reservation ineligible and children are always 0; the meal plan
is read with English word lists and a missing meal row becomes "no meals", which can produce a false
savings alert; stay dates need one exact format; a hotel link with a query string loses the property.

## Functional requirements

- **FR-1.** Jev reads adults, children, rooms and nights from the lines above the room section, in
  the same two calls as the total, refund and room. Every answer must agree at 0.5 or more, and the
  nights must equal the stay dates; otherwise the party stays unknown. The code party parser is removed.
- **FR-2.** Jev classifies the booked meal plan (none, breakfast, half board, full board, all
  inclusive, not stated) from the room section and names the line stating it. "Not stated" or no
  agreement leaves it unknown, so the stay is never compared on a guessed meal plan. The code meal
  reader, including the "no meal row means no meals" rule, is removed.
- **FR-3.** Stay dates stay read by code (they prove sync completeness even when TypeSafe is down);
  when code cannot read them, Jev reads month, day and year for both dates, and code checks them.
- **FR-4.** A hotel link with a query string or fragment keeps the property; the query is dropped.
- **FR-5.** No guest name, email, phone, confirmation number or PIN is sent to TypeSafe.
- **FR-6.** The stall message names the facts that are missing.

## Out of scope

Price-check decisions (release B); discovery gates and trip cards (release C); child ages.
