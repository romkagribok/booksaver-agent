---
version: jevreader-d0424de
commit: d0424de0624
created: "2026-11-04T16:07:08Z"
status: deployed-awaiting-readback
recorded: "2026-11-04T16:07:27Z"
---

# Jev is the only reader of reservation totals and refund terms (intent 030, unit 1)

## Change

Bolt 098 (ADR-061, superseding ADR-060): Jev alone reads the booked total and refund terms on every
upcoming confirmation (two agreeing runs; layout-independent checks). The code parser's price and
cancellation parsing, the comparison, the owner disagreement notice and the alert label are gone.
Dated cost lines are deadline candidates; "within ..." uses calendar months. Cause: the comparison
produced a false disagreement on 2026-11-04 from its own date arithmetic.

## Artifact and verification

- PR #97, head `d0424de`; merge `3f5c2b14bf34`, `src` identical.
- Image `booksaver-agent:jevreader-d0424de` =
  `sha256:303ac7173e9cf154fca47c255e942f098fe81507ddadb249c4fe7513fd2e83b7`, built on
  `jevfacts-2938b8f`.
- Quality: 3,260 passed, 1 skipped; Ruff and mypy clean; AI-DLC validators 0 errors.
- Review: Codex clean on `d0424de` with no findings; `scripts/codex_merge_gate.py 97` passed.
- Dev on the exact image: 136 modules match, pins matched, schema, foreign keys, Chromium, clean stop.
- Live replay on the exact image (kit `jevonly-20261104`, cloned data): all seven of the owner's and
  dad's reservations correct, Kalipè now monitored; one refund answer unread and its saved value kept.
- Promotion: backup `/opt/booksaver-backups/jevreader-d0424de-20261104`, healthy, schema 23, public
  health passed, Caddy unchanged, at 2026-11-04T16:07:08Z. Rollback tag
  `booksaver-agent:rollback-pre-jevreader-d0424de`; no schema change.

## Production read-back

Pending: owner's scheduled run 2026-11-04T19:58Z, the dad's 23:23Z.
