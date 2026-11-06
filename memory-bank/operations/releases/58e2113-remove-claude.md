---
version: releaseb-58e2113
commit: 58e2113
created: "2026-11-06T16:23:03Z"
status: deployed-awaiting-readback
recorded: "2026-11-06T16:24:00Z"
---

# Claude code, data and configuration removed (intent 030 release B)

## Change

Bolt 100 (steps 1 and 2) and bolt 101 (ADR-063): all Anthropic, Stagehand and Browser Use agent code,
the scripted price path, the legacy inventory source, the model-policy layer, evaluation CLI,
`/setkey` and `/deletekey` removed; schema v24 drops the Claude tables and clears personal keys;
Claude-era config keys are ignored with one warning.

## Artifact and verification

- PRs #102 (merge `fefc5e93b33c`) and #103 (head `58e2113`, merge `cd9de0415fcf`), both Codex clean
  with no findings; `src` identical to main.
- Image `booksaver-agent:releaseb-58e2113` =
  `sha256:997834edc7847bd1c2aa1113bea3d22dc2c2d64e5b1986cc9afd0532cff5b532`, built on
  `releasea-4b9a108` with the clean-tree kit Dockerfile (deleted modules removed from `/app/src`,
  `/app/build` and site-packages; `stagehand` and `browserbase` uninstalled); 116 modules.
- Quality: 2,600 passed, 1 skipped; Ruff and mypy clean; AI-DLC validators 0 errors.
- Live replay on the clean image with cloned data and no key: all syncs complete, owner's Jev check
  success, schema 24 with no `llm_` tables.
- Promotion: backup `/opt/booksaver-backups/releaseb-58e2113-20261106`, healthy, schema 24, public
  health passed, at 2026-11-06T16:23:03Z. Rollback tag `booksaver-agent:rollback-pre-releaseb-58e2113`
  (rolling back also needs the backup database, since v24 dropped tables).
- Config: retired keys removed from `/opt/booksaver-agent/config.toml` (`[agent]` max_steps,
  max_llm_calls, check_timeout_seconds; `routing`; `max_llm_calls_per_user_per_day`); restarted
  healthy with no retired-key warning (original in the backup).

## Production read-back

Pending: scheduled runs from 2026-11-06T21:19Z.
