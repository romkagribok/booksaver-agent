---
stage: test
bolt: 113-legible-reports
created: 2026-11-11T00:26:06Z
---

# Test Report: legible-reports

- **Unit:** 2,625 passed, 1 skipped; ruff and mypy clean.
  - New tests: the ended deadline (two wordings), a date that may still be running, stay and time
    formats, price comparisons, a plain sentence for every `FailureCode`, the free-cancellation
    line in `/bookings`, the `/savings` layout without IDs, and the check-now note under the
    minimum.
  - Tests that asserted the old wording were updated.
- **Offline Jev check on the real Aloft page** (captured 2026-11-10, kit `legible-20261111`, three
  runs each): production left the terms unread 3 of 3 times. The candidate read "Free cancellation
  ended on 29 Oct 2026." 3 of 3 times.
- **Staged replay 00:21–00:24Z on 2026-11-11** (cloned data, no notifications, daemon paused and
  restored healthy):
  - User 4's sync was complete, 7 discovered and 5 eligible, and every fact on all 5 opened pages
    was read.
  - Aloft is now "current" (check-in today), so its page is no longer opened.
  - The `/bookings`, `/savings` and `/checks` replies rendered from that data for users 4 and
    1 contain no IDs, codes or profiles.
