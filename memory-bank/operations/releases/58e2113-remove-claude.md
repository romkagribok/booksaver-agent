---
version: releaseb-58e2113
commit: 58e2113
created: "2026-11-06T16:23:03Z"
status: deployed-verified
recorded: "2026-11-10T00:52:50Z"
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

Read 2026-11-10T00:45:49Z to 00:49:23Z; window 2026-11-06T16:23:03Z (promotion) to 2026-11-09T20:59Z. Method: read-only, through the specs.md operations agent's verify step: `ssh booksaver`, `docker ps/inspect/events/logs`, and the live database opened read-only from the host volume (`mode=ro`); the app's store was not opened and nothing was stopped, restarted, written or replayed.

- Scope: no scheduled run happened on `releaseb-58e2113` itself (live until 17:25:14Z); every observation is from the later images built on it (`noavail-39a666b`, `jevroom-86279b0`, `jevfacts-21694ab`).
- Jev only: 32 syncs for users 1, 3 and 4 (30 scheduled, 2 `bookings`), all with `fallback_used = 0`, model cost 0 and no Claude recovery calls; 45 price checks, the 23 successes all `llm` (Jev, no fallback); 64 Jev runs, only `observed` or `unavailable`; 0 `price_comparisons` rows; 0 of 42 traces mention `anthropic`, `claude` or `stagehand`. Scheduled slots: 30 completed, 0 missed.
- Failures unrelated to the removal: user 4's 2026-11-07T09:05Z sync `navigation_failed` (next run fine); two `incomplete` syncs preserved by policy (user 4 manual at 2026-11-09T06:11Z, user 3 scheduled at 20:23:32Z); `no_equivalent_offer` and the daily check limit on price checks.
- Schema: version 24 applied 2026-11-06T16:22:53Z; no `llm_` tables; `encrypted_key` empty for users 1, 3 and 4.
- Config: the live `config.toml` (names only; modified by another session at 2026-11-10T00:41:37Z) has none of the retired keys; the 00:41:54Z startup shows no retired-key warning. The "one warning when old keys are present" behaviour was not seen in production, because the keys were removed before the first startup; tests cover it. No `anthropic`, `claude`, `stagehand`, `browserbase` or `openai` variable in the container, compose file or `.env`; `stagehand` and `browserbase` are not installed; `anthropic` stays only as a browser-use dependency.
- Source: 0 `anthropic` or `stagehand` imports in the deployed kit's `src` (the image's `/app/src` was not grepped).
- Caveat, logs: daemon logs since the promotion no longer exist. Another session recreated the `booksaver` container at 2026-11-10T00:41:38Z (Docker json-file logs go with the container), so `docker logs` starts at 00:41:54Z with five clean startup lines. "No errors" rests on database outcomes (`booking_sync_runs`, `check_history`, `jev_price_runs`, `scheduled_check_slots`, `monitoring_stall_notices`) and the later promotion health logs, not on a log scan.
- Caveat, production state at read-back: at 2026-11-10T00:49Z the `booksaver` daemon was `Exited (0)`, paused at 00:46:37Z by a concurrent session's `jevprice-20261110` staging kit (its marker says its `run.sh` restores it). Not caused by this release; its restore was not observed in this read-back.

Verdict: passed with the caveats above. Issues #79 and #3 (US-253) were closed with this close-out; see the bolt 101 test report.
