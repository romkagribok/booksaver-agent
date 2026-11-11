---
version: legible-8fab90f
commit: 8fab90f
created: "2026-11-11T00:33:12Z"
status: deployed
recorded: "2026-11-11T00:33:45Z"
---

# Accurate, legible reports for users (intent 040)

## Change

Bolt 113 (US-265, US-266, US-267).
- **Ended free cancellation:** a passed free-cancellation date (a full day plus the timezone margin
  after it) is recorded as not refundable, with "Free cancellation ended on <date>." Before, it
  counted as unread on every sync (Aloft, user 4).
- **`/bookings`:** readable stay dates, "Free cancellation until <date>", and plain reasons.
- **`/savings`:** hotel, stay, price paid, price found, the saving, and when it was found. No IDs.
- **`/checks` and `/checknow`:** hotel, stay and price paid, then each check in plain words. No
  failure codes, check IDs or browser profiles. `/checknow` notes savings under the 5-unit alert
  minimum.
- **Alert:** "Checked as: signed in to your Booking.com account", and "Genius prices were shown"
  when they were.

## Artifact and verification

- PR #121, head `442fbab`, merge `8fab90fcdbe8`. Codex rounds:
  - `c0dd732`: P2. Per-check spending limits were worded as "today's budget is used up". Fixed in
    `442fbab`, which reserves that wording for the daily limit.
  - `442fbab`: no findings.
  - `scripts/codex_merge_gate.py 121` passed (exit 0) before the merge.
- Image `booksaver-agent:legible-8fab90f` =
  `sha256:81768c5fc03124d49d62e7c8b06784b4c6afcde712e8b42c11f1162d8a7beca2`. Built from the
  merge's `git archive` on `minsave-52c1330`; 117 modules.
- Quality: 2,626 passed, 1 skipped. Ruff and mypy clean. AI-DLC validation found 0 inconsistencies.
- Development: config and requirements valid in the image. The budget wording was checked in the
  image.
- Staging:
  - Candidate `9a0784a` (kit `legible-20261111`): the real Aloft page (captured 2026-11-10) was
    read three times with Jev. Production left the terms unread 3 of 3 times; the candidate read
    "Free cancellation ended on 29 Oct 2026." 3 of 3 times.
  - Staged replay 00:21–00:24Z (cloned data, no notifications, daemon restored healthy): the user 4
    sync was complete (7 discovered, 5 eligible) and every fact on all 5 opened pages was read.
    The `/bookings`, `/savings` and `/checks` replies for users 4 and 1 were free of IDs and
    codes.
  - The release source (merge, which differs from the candidate only in the budget wording) rendered
    `/bookings`, `/checks` and `/savings` on a copy of production data before promotion.
- Promotion: backup `/opt/booksaver-backups/legible-8fab90f-20261111`. Healthy, SQLite integrity,
  schema 24, public health passed, Caddy unchanged at 2026-11-11T00:33:12Z. Rollback tag
  `booksaver-agent:rollback-pre-legible-8fab90f`; no schema change.

## Production read-back

Pending: user 1's scheduled run at 03:54Z and user 4's at 07:35Z on 2026-11-11.
