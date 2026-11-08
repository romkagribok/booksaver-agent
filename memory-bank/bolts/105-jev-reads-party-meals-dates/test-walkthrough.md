---
stage: test
bolt: 105-jev-reads-party-meals-dates
created: 2026-11-08T18:45:20Z
---

# Test Walkthrough

- Unit: party read, children read, nights mismatch and "not stated" rejected; meal class and line read,
  "not stated" and disagreement unknown; guest name, email and phone never sent; Jev dates fill unknown
  dates, set the lifecycle and feed the refund check, and are not asked when code read dates; impossible
  dates rejected; multi-room party gets no room type; hotel link query dropped; stall message names
  missing facts. Full suite 2,591 passed, 1 skipped; Ruff and mypy clean.
- Offline with live Jev on the eight captured real pages (kit `jevfacts-20261108`): party, meals and
  room equal the previous code readings on all seven distinct reservations. Variants: "2 adults, 1 child"
  read as 2/1/1; reworded breakfast read as breakfast; breakfast for an extra US$15 read as none; meal
  row removed read as unknown; dates in an unsupported format read correctly.
- Replay of users 4, 1 and 3 on cloned data (restored healthy at 18:44:59Z): all syncs complete; all
  seven upcoming reservations unchanged (party, meal text, room, total, refund, eligibility); Jev cost
  for user 4's sync 12 calls, 57,604 input tokens, about USD 0.0024.
