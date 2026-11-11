---
version: minsave-52c1330
commit: 52c1330
created: "2026-11-10T14:57:41Z"
status: deployed-verified
recorded: "2026-11-10T23:58:29Z"
---

# No alert for a saving under 5 in the booking currency (intent 039)

## Change

Bolt 112 (US-264). `detect_savings` rejects a saving below `MINIMUM_SAVING` (5 of the booking's
own currency) with `saving_below_minimum`. Exactly 5 is still an opportunity.

## Artifact and verification

- PR #119, head `34eb726`, merge `52c13305fec3`. Codex reviewed `34eb726`: no findings.
  `scripts/codex_merge_gate.py 119` passed (exit 0) before the merge.
- Image `booksaver-agent:minsave-52c1330` =
  `sha256:c97ab11fe28aa88131bdd490edcdc407d5e812c56e3335653c5fdad6c141921d`. Built from the
  merge's `git archive` on `currency-ed5fc6d`; 116 modules.
- Quality: 2,575 passed, 1 skipped. Ruff and mypy clean. AI-DLC validation found 0 inconsistencies.
- Development: config and requirements valid in the image.
- Staging: the image's `detect_savings` was run on that day's production values.
  - Ayres EUR 133 → 132 (saved 1): `saving_below_minimum`.
  - Union Club USD 592.48 → 570 (saved 22.48): opportunity.
- Promotion: backup `/opt/booksaver-backups/minsave-52c1330-20261110`. Healthy, SQLite integrity,
  schema 24, public health passed, Caddy unchanged at 2026-11-10T14:57:41Z. Rollback tag
  `booksaver-agent:rollback-pre-minsave-52c1330`; no schema change.

## Production read-back

Scheduled checks on 2026-11-10 after the promotion:
- **User 1, Union Club, 19:02:24Z:** USD 570 against 592.48. The USD 22.48 opportunity was stored
  and notified at 19:02:24Z.
- **User 4, Ayres, 18:54:55Z:** USD 144 against 147.78. The saving of 3.78 was rejected, and no
  opportunity was stored or alerted.
- No opportunity under 5 has been stored since the promotion. Telegram polling had transient
  connection resets, which retried; alert delivery was not affected.
