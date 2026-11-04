---
version: jevfacts-2938b8f
commit: 2938b8f498
created: "2026-11-04T00:59:30Z"
status: deployed-awaiting-readback
recorded: "2026-11-04T01:00:01Z"
---

# Jev reads reservation totals and refund terms; code wins where it reads (intent 029)

New Booking.com layouts had left reservations silently unmonitored: on 2026-11-03 none of the
owner's dad's four refundable stays, and not the owner's rebooked Union Club stay.

## Change

Bolt 097 (ADR-060): Jev reads the total, refundability and deadline sentence on every upcoming
confirmation, asked twice; code checks only layout-independent rules and wins where it reads.
Disagreements reach the owner once a day. Jev-read totals (schema v23 `booked_total_source`,
`baseline_source`) fill gaps, never replace a saved total, and are labelled in alerts. Unreadable
upcoming stays get the stall message; sync limit 300 s, jobs 480 s.

## Artifact and verification

- PR #95, head `2938b8f`; merge `d6ee51d9b300`, `src` identical.
- Image `booksaver-agent:jevfacts-2938b8f` =
  `sha256:06ce3af490dcd5bc06525c4a50cd89f2bd5d3d1785caa8f38618f885a548f7af`, built on
  `stallnotice-0293d72`.
- Quality: 3,379 passed, 1 skipped; Ruff and mypy clean; AI-DLC validators 0 errors.
- Review: Codex, six rounds. Nine findings against the first design (a parallel code proof) led to
  the owner-approved redesign; one finding on the redesign fixed; clean on `2938b8f`;
  `scripts/codex_merge_gate.py 95` passed.
- Reliability measurement (7 real reservations, 3 runs): total 21/21, refundability 21/21.
- Dev on the exact image: 136 modules match, pins matched, schema, foreign keys, Chromium, clean stop.
- Live replay on the exact image (kit `jevfacts-20261103`, cloned data): dad 6/6 complete with three
  refundable stays eligible and both non-refundable stays correct; owner's stay eligible at USD
  592.48; Jev agreed on all 6 cross-checked facts. One earlier replay of the same code stopped after
  two pages on a Booking.com navigation failure (`detail_navigation`); unseen pages were preserved
  and the next replay completed. Kalipè's refund terms were filled in one replay and not the next
  (Jev's two answers did not both reach 0.6); a filled value persists in production.
- Promotion: backup `/opt/booksaver-backups/jevfacts-2938b8f-20261104`, healthy, schema 23, public
  health passed, Caddy unchanged, at 2026-11-04T00:59:30Z. Rollback tag
  `booksaver-agent:rollback-pre-jevfacts-2938b8f`; the v23 columns are additive.

## Production read-back

Pending: owner's scheduled run 2026-11-04T06:07Z, the dad's 13:56Z.
