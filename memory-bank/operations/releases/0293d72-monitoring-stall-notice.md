---
version: stallnotice-0293d72
commit: 0293d722d8
created: "2026-11-03T03:44:43Z"
status: deployed-awaiting-readback
recorded: "2026-11-03T03:45:20Z"
---

# Stalled monitoring is reported to the user (intent 028, release 2)

## Change

Bolt 095: after a scheduled run, a monitored upcoming reservation with no conclusive result for 24
hours sends its own user one Telegram message with the reason, then one when it recovers. Schema v22
adds `monitoring_stall_notices`.

## Artifact and verification

- PR #92, head `0293d72`; merge `69924fbbedbe`; deployed from main `4833d9e`, `src` identical.
- Image `booksaver-agent:stallnotice-0293d72` =
  `sha256:2f1510148e00c4393833f0f267642f9e88b1bd8f23d3c8c8c21fd30d3a6e3d82`, built on
  `reschange-f54b7b7`.
- Quality: 3,346 passed, 1 skipped; Ruff and mypy clean; AI-DLC validators 0 errors.
- Review: Codex found two issues (recovery missed when a new stall began; a blocking incomplete sync
  misnamed), fixed with tests; clean on `0293d72`; `scripts/codex_merge_gate.py 92` passed.
- Dev on the exact image: 135 modules match, pins matched, schema, foreign keys, Chromium, clean stop.
- Copied production database migrated to schema 22 with integrity and foreign keys clean; only the
  owner's reservation could notify, and a scheduled run reports after its check.
- Promotion: backup `/opt/booksaver-backups/stallnotice-0293d72-20261103`, healthy, schema 22,
  public health passed, Caddy unchanged, at 2026-11-03T03:44:43Z, before the owner's first run on
  release 1 (both releases had passed live staging). Rollback tag
  `booksaver-agent:rollback-pre-stallnotice-0293d72`; the v22 table is additive.

## Production read-back

Pending, with release 1's: the owner's run at 2026-11-03T05:38Z.
