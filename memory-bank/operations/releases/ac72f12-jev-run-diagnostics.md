---
version: jevdiag-ac72f12
commit: ac72f121ff7f762989dff786f155b980ddba3701
created: "2026-10-04T03:24:21Z"
status: complete
recorded: "2026-10-10T01:49:55Z"
---

# Jev run diagnostics — released

Recorded retroactively on 2026-10-10 from the release kit logs; no record was written at the time.

## What changed

Every Jev run keeps a content-free diagnostic (PR #76), added after a run on 2026-10-03T22:11Z
ended without a price and nothing explained why.

## Artifact and verification

- Source `ac72f12` (PR #76); merge `f9b653da02beaeab543c603863d4cac1e2427918`, tree identical.
- Image `booksaver-agent:jevdiag-ac72f12` =
  `sha256:09b421e71df3e86cf290671471110784c79535dfc9245d0f7149226cc30e3bf2`, built on
  `jevtotal-18f367e`.
- Quality: 3,092 tests, one skip; Ruff and mypy clean; AI-DLC validators 0 errors.
- Bugbot: **waived** (Cursor usage limit on head `ac72f12`).
- Dev on the exact image: installed source and pins matched, `pip check`, smoke, three supervisor
  cleanup cases. No stage probe was run.
- Production: promoted 2026-10-04T03:24:21Z with backup
  `/opt/booksaver-backups/jevdiag-ac72f12-20261003` and rollback tag
  `booksaver-agent:rollback-pre-jevdiag-ac72f12`; healthy, zero restarts, no published ports,
  SQLite integrity ok, schema 19.

## Finding during promotion

One Chromium started by the existing Browser Use price method at 2026-10-03T18:04:44Z was still
running 9.3 hours later (about 800 MB of the 2 GB limit, holding an invitee's signed-in session).
Its start matched a baseline run that timed out after 35 seconds. The recreate cleared it; container
memory went from 1,207 MB to 40 MB. The teardown defect is not fixed. Process listing saved as
`/opt/booksaver-releases/jevdiag-20261003/orphan-browser-evidence.txt`.

## Outcome

On 2026-10-09 the diagnostic identified the cause of two further failed runs: Booking.com's error
page with nothing to click, on which Jev chose WAIT six times.
Evidence: `/opt/booksaver-releases/jevdiag-20261003/`.
