---
version: jevbetter-3cdaf88
commit: 28abf16
created: "2026-11-10T01:42:19Z"
status: deployed-verified
recorded: "2026-11-10T01:43:08Z"
---

# Unenforced booking cap and retired-keys list removed (intent 036, bolt 108)

## Change

US-260: `[limits] max_bookings_per_user` (configured, never enforced) is removed, along with the
retired-keys list (`_IGNORED_KEYS`) and its startup warning; `load_config` already ignored unknown
keys. Production's two stale config lines were deleted.

## Artifact and verification

- PR #113, merge `28abf16`; Codex clean with no findings on `ba0ae5c`; `codex_merge_gate.py 113` passed.
  Quality: 2,555 passed, 1 skipped; Ruff and mypy clean.
- Before merge: #113 source over `booksaver-agent:latest`, `--network none`, with production's
  `config.toml` mounted read-only (stale lines still present): `booksaver config validate` exit 0,
  "Config is valid." (kit `/opt/booksaver-releases/rmbookingcap-20261110`).
- Shipped inside the same-or-better release image, not separately: `booksaver-agent:jevbetter-3cdaf88` =
  `sha256:eea523a101aaf9a9d10f6f9e7a7276b91b24f788040ef7bf2c9aa6697a1982ba`, built from main merge
  `3cdaf88` (PR #112), which contains `28abf16`; promoted 2026-11-10T01:42:19Z by the release B
  session (backup `/opt/booksaver-backups/jevbetter-3cdaf88-20261110`, rollback tag
  `rollback-pre-jevbetter-3cdaf88`).

## Production read-back and config change

- 2026-11-10T01:42:38Z: container running healthy on `eea523a1`, 0 restarts; deployed checkout has
  `28abf16`; installed `LimitsSettings` has no `max_bookings_per_user`, `load_config` has no
  `_IGNORED_KEYS` and no "no longer have any effect" warning; that warning absent from startup logs.
- 2026-11-10T01:42:46Z: `/opt/booksaver-agent/config.toml` lines `rebook_confirm_timeout_seconds = 600`
  (`[telegram_bot]`, read by nothing) and `max_bookings_per_user = 3` deleted; written in place (same
  inode, so the read-only bind mount sees it without a restart). Backup
  `config.toml.pre-rmstale-20261110T014246Z`. `booksaver config validate` in the running container:
  "Config is valid."; no restart; container healthy. Rollback: restore the backup.
