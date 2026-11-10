---
stage: test
bolt: 110-jev-classifies-trip-cards
created: 2026-11-10T02:21:59Z
---

# Test Walkthrough

- Unit: 2,568 passed, 1 skipped; ruff, mypy, AI-DLC validation clean. New tests show the code path
  dropping an active hotel when "Confirmed" is renamed (count matches on the cancelled card) and the
  Jev path opening it; flights verifying a count; completed skips; unclassified cards opened; outage
  fallback; a non-reservation "stay" rejected; classifier agreement, privacy and budget.
- Capture (kit `tripcards-20261110`, daemon paused 02:01–02:06Z): real trip pages of users 4 and 1
  (hotel cards, cars.booking.com rentals, a cancelled duplicate, Manage aliases, promotions).
- Offline Jev: 29 cards (all captured cards, renamed statuses, flight, tour, taxi, cancelled car,
  German statuses, promotions): 29 correct, 0 unsure.
- Staged replay (daemon paused 02:16–02:21Z, cloned data): users 4, 1, 3 syncs complete; all cards
  classified at 0.8+; 7 + 2 reservations discovered as before. Only change: Ayres' booked total EUR
  133 -> 132 from the existing confirmation reader (a euro display of a US-dollar stay), unrelated
  to cards. User 4 sync Jev cost about USD 0.0028.
