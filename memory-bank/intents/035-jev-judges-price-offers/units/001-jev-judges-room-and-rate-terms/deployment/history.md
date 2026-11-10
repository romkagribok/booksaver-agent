---
version: jevbetter-3cdaf88
environment: production
created: 2026-11-10T13:53:59Z
status: complete
---

# Deployment and verification history

| Version | Merge | Image | Promoted | Release record |
|---|---|---|---|---|
| jevprice-003d03f | 003d03f | sha256:c644867e… | 2026-11-10T01:07:59Z | ../../../../operations/releases/003d03f-jev-judges-price-offers.md |
| jevbetter-3cdaf88 | 3cdaf88 | sha256:eea523a1… | 2026-11-10T01:42:19Z | ../../../../operations/releases/3cdaf88-same-or-better-room.md |

Build → Development (installed-source check) → Staging (paused-daemon replays on cloned data, kits
`jevprice-20261110`, `jevbetter-20261110`) → Production promotion with backup and rollback tag →
production read-back on the 2026-11-10 scheduled checks. Superseded in production by
`tripcards-db3207b` (2026-11-10T02:35:55Z), which contains both.
