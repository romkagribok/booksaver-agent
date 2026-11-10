---
version: tripcards-db3207b
commit: db3207b
created: "2026-11-10T02:35:55Z"
status: deployed-verified
recorded: "2026-11-10T02:40:00Z"
---

# Jev classifies trip cards (intent 037, release C)

## Change

Bolt 110 (US-262, ADR-066).
- **Jev classifies every card on a trip page:** stay active, completed or cancelled; other booking
  active or inactive; not a booking. It is asked twice, and both answers must agree at 0.8.
- **How the classes are used:** they drive the count check (every card must be classified), which
  cards are opened, completed-stay skips and cancellation claims. Unclassified cards, including any
  beyond the first 30, are opened and block count proof.
- **Privacy:** card lines are redacted before they reach TypeSafe.
- **Outage fallback:** the code status words are used only when TypeSafe has no answer.

## Artifact and verification

- PR #116, head `3178c19`, merge `db3207bfef2d`. Codex rounds:
  - `3d9e1e9`: P1 (cards beyond 30 dropped without blocking proof) and P2 (label values reached
    TypeSafe). Both fixed in `d5a2af9`.
  - `d5a2af9`: P2 (single-line car-booking links left out). Fixed in `3178c19`.
  - `3178c19`: no findings.
  - `scripts/codex_merge_gate.py 116` passed (exit 0) before the merge.
- Image `booksaver-agent:tripcards-db3207b` =
  `sha256:a2ea1ef5efe1bca17232462a2a56618a7bf540abb30ef37651ed62edf9b064d6`. It was built from the
  merge's `git archive` on `jevbetter-3cdaf88` with the clean-tree kit Dockerfile; 116 modules.
- Quality: 2,570 passed, 1 skipped. Ruff and mypy clean. AI-DLC validation found 0 inconsistencies.
- Capture of real trip pages (kit `tripcards-20261110`; daemon paused 02:01–02:06Z).
- Offline Jev check on 29 cards (captured, renamed statuses, flight, tour, taxi, cancelled car,
  German, promotions): 29 correct, 0 unsure.
- Staged replay (02:16–02:21Z): users 4, 1 and 3 syncs complete, every card classified, and the same
  reservations discovered as before.
- Promotion: backup `/opt/booksaver-backups/tripcards-db3207b-20261110`. Healthy, schema 24, public
  health passed, Caddy unchanged at 2026-11-10T02:35:55Z. Rollback tag
  `booksaver-agent:rollback-pre-tripcards-db3207b`; no schema change.

## Production read-back

Production syncs on 2026-11-10:
- **User 3:** 05:18Z and 08:31Z, complete, no bookings.
- **User 4:** 06:52Z and 09:47Z, complete, 7 discovered and 5 eligible as before, cards classified
  on both trip pages (`cards_classified=2`).
- **User 1:** 11:43Z, complete, 2 discovered (`cards_classified=1`).
- No stall notices; no incomplete sync.
