---
version: jevtotal-18f367e
commit: 18f367e6bf2386de129b724ad2ee54d767c31e93
created: "2026-10-01T05:35:31Z"
status: complete
recorded: "2026-10-10T01:49:55Z"
---

# Jev total-price question fix and key activation — released

Recorded retroactively on 2026-10-10 from the release kit logs; no record was written at the time.

## What changed

- The owner had added the TypeSafe key to `.env` as `BOOKSAVER_TYPESAFE_AI_KEY`; the daemon reads
  `BOOKSAVER_TYPESAFE_API_KEY`. The variable was renamed in place at about 2026-10-01T05:29Z
  (backup `/opt/booksaver-agent/.env.pre-typesafe-rename`) and the container recreated.
- First live TypeSafe calls showed the whole-stay total question answering "none" for every
  one-night rate card. PR #75 states the stay length and Booking.com's price labelling
  (cohort `jev-price-v2`).

## Artifact and verification

- Source `18f367e` (PR #75); merge `a29e5bb8992d3379bb028a473360588609d9ce63`, tree identical.
- Image `booksaver-agent:jevtotal-18f367e` =
  `sha256:c9139ba678448d88d3a8426fa2b009d41158ccbaf1888d58a10e70791db0644f`, built on
  `jevcmp-e6452e6`.
- Quality: 3,083 tests, one skip; Ruff and mypy clean. Live model check: the patched request
  grounded 10 of 10 cases.
- Bugbot: **waived** (Cursor usage limit on head `18f367e`).
- Dev on the exact image: installed source and pins matched, `pip check`, smoke, three supervisor
  cleanup cases. No stage probe was run (no schema or coordinator change).
- Production: promoted 2026-10-01T05:35:31Z with backup
  `/opt/booksaver-backups/jevtotal-18f367e-20261001` and rollback tag
  `booksaver-agent:rollback-pre-jevtotal-18f367e`; healthy, zero restarts, no published ports,
  SQLite integrity ok, schema 19.

Live acceptance: the owner confirmed a two-row report on 2026-10-01.
Evidence: `/opt/booksaver-releases/jevtotal-20261001/`.
