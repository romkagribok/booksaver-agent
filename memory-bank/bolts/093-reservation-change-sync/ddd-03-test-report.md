---
unit: 001-reservation-change-sync
bolt: 093-reservation-change-sync
stage: test
status: complete
created: 2026-11-03T00:56:28Z
updated: 2026-11-03T00:56:28Z
---

# Test Report - Reservation Change Sync

## Summary

- Full suite on the branch: 3,322 passed, 1 skipped, 52 existing warnings; Ruff clean; mypy clean for
  133 modules. Coverage is not part of the repository gate.
- Reader: observed converted shape and 11 refusal shapes. Persistence: date change, room, occupancy, refund change, hold and resume of the same booking, unchanged stay keeps its total, and four cases that still fail closed (provider-submitted, one date, cancelled page, other hotel).

## Live replay on the candidate image

Image `booksaver-agent:reschange-8faf528`, the owner's real page, with the daemon paused and a
cloned database (kit `reschange-20261103`, `stage-live.log`; no notifications):

- Sync: `complete`, eligible 1, no conflict. Reservation and booking moved from 2026-11-24 to
  2027-04-15/16, deadline 2027-04-12, baseline USD 346.08 to USD 659.68, same booking.
- Saved opportunities on that booking: 22 before the sync, 0 after it. Check history kept (134).
- One Jev check: `PIN_CURRENCY` taken once, 8 offers accepted and 3 rejected as not explicitly
  refundable, no `currency_mismatch`; outcome success, live USD 581; one opportunity created. Model
  cost about USD 0.00075.
- Dev on the exact image: 133 installed modules match source, pinned versions match, schema, foreign
  keys, Chromium and clean daemon stop passed.
