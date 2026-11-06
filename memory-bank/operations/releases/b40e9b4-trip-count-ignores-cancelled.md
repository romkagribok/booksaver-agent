---
version: tripcount-b40e9b4
commit: b40e9b4
created: "2026-11-06T00:26:12Z"
status: deployed-verified
recorded: "2026-11-06T01:23:40Z"
---

# A cancelled card no longer makes a trip unverifiable (intent 031)

## Change

Bolt 102: `count_matches` accepts a trip page's cards with or without cancelled or completed cards,
because Booking.com's trip count omits cancelled bookings.

## Artifact and verification

- PR #99, merge `eec835aabfb6`, `src` identical; image `booksaver-agent:tripcount-b40e9b4` =
  `sha256:6cf3bc3ee37e9b9817dd3a3ca2055370fdeb486d036b3cb5ce16f34ae3cebdf3`.
- Quality: 3,261 passed, 1 skipped; Ruff, mypy clean. Codex clean with no findings.
- Live replay on cloned data: the dad's and the owner's syncs complete; the superseded reservation
  retired.
- Promotion: backup `/opt/booksaver-backups/tripcount-b40e9b4-20261106`, healthy, schema 23.

## Production read-back

2026-11-06T01:10Z: the dad's scheduled sync completed (six discovered); the superseded Best Western
(USD 521.11) is `absent` and ineligible, so no stall message for it; the new one checked successfully.
