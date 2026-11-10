---
unit: 003-delete-claude-code
bolt: 100-delete-claude-code
stage: test
status: complete
created: 2026-11-06T03:03:29Z
updated: 2026-11-10T00:54:56Z
---

# Test Report - Delete the Claude Code

## Step 1 (PR #102, merged)

3,109 passed, 1 skipped; live replay with no Anthropic key identical to release A.

## Step 2 (with bolt 101)

- Full suite 2,600 passed, 1 skipped (tests of deleted code removed); Ruff clean; mypy clean for 116
  modules; no source file imports `anthropic` or `stagehand` or reads `BOOKSAVER_LLM_API_KEY`.
- Source: about 53,600 lines before the cleanup, 32,936 after (step 1 about -11,000, step 2 about
  -26,000 including tests).
- Image: the release Dockerfile layered new source over the old tree, so deleted modules survived in
  `/app/src`, `/app/build` and site-packages. The kit Dockerfile now clears all three and uninstalls
  the old package and `stagehand`; the candidate holds 116 modules and only `typesafe_client.py` in
  `llm/`.
- Live replay on the clean image (kit `releaseb2-20261106`, cloned data, no key): owner, dad and the
  third invitee sync complete with unchanged facts; owner's Jev check success at USD 581; migration
  to schema 24 dropped the three Claude tables; no personal keys stored; the production config loads
  with one retired-key warning.
- Production qualification state checked read-only: none stored, so collapsing routing changes no
  user's path.

## Production evidence (2026-11-10T00:54:56Z)

Read-only read-back 2026-11-10T00:45:49Z to 00:49:23Z through the specs.md operations agent's verify step;
Release record `memory-bank/operations/releases/58e2113-remove-claude.md`. No scheduled run happened on
`releaseb-58e2113` itself; the evidence is from the later images built on it.

| Story | Criterion | Status |
|-------|-----------|--------|
| US-249 | Jev and the grouped reader import nothing from Claude-only modules | ✅ deployed kit `src` has 0 `anthropic`/`stagehand` imports; Jev and the reader ran 32 syncs and 64 Jev runs for users 1, 3 and 4 |
| US-250 | No module imports anthropic or stagehand | ✅ 0 imports in the checkout and the deployed kit `src`; `stagehand` and `browserbase` not installed (the image's `/app/src` was not grepped) |
| US-250 | Full suite and live replay match unit 2 | ✅ 2,600 passed, 1 skipped; replay and production: only Jev checks (23 successes, all `llm`, no fallback), 30 scheduled slots completed, 0 missed |

Caveats: Daemon logs from the promotion to 2026-11-10T00:41Z no longer exist (another session recreated the container at 00:41:38Z), so "no errors" rests on database outcomes and the later promotion health logs. Unrelated failures: one `navigation_failed` sync (user 4, 2026-11-07T09:05Z) and two
syncs `incomplete` by the preservation policy (user 4 manual 2026-11-09T06:11Z; user 3 scheduled
20:23:32Z on a different inventory path).

The test-stage stop for completion was not held; it is covered by the owner's standing waiver of
2026-11-09 ("human checkpoints may be skipped as they have been, I am under control").
