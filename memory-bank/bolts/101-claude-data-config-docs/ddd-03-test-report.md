---
unit: 004-claude-data-config-docs
bolt: 101-claude-data-config-docs
stage: test
status: complete
created: 2026-11-06T03:03:29Z
updated: 2026-11-10T00:54:56Z
---

# Test Report - Claude Data, Config and Docs

Covered by the bolt 100 step 2 run: production config loads with one warning listing the retired
keys; a config without them warns nothing; the v24 migration drops the tables and clears keys on
cloned production data (schema 24, no `llm_` tables, no personal keys).

Not done: `.env.example` still names `BOOKSAVER_LLM_API_KEY`; a local deny rule prevents reading or
editing `.env*` files. The owner is asked to remove that line.

## Production evidence (2026-11-10T00:54:56Z)

Read-only read-back 2026-11-10T00:45:49Z to 00:49:23Z through the specs.md operations agent's verify step;
Release record `memory-bank/operations/releases/58e2113-remove-claude.md`.

| Story | Criterion | Status |
|-------|-----------|--------|
| US-251 | Migration drops the three Claude tables and clears personal keys | ✅ schema 24 applied 2026-11-06T16:22:53Z after the backup; no `llm_` tables; `encrypted_key` empty for users 1, 3 and 4 |
| US-252 | A config with Claude model keys loads with one warning | ✅ in the cloned-data run above and in tests; not seen in production because the keys were removed from the live config before the first startup; the latest startup shows no warning |
| US-253 | README, AGENTS.md, the example config and the standards name TypeSafe as the only model provider | ❌ README, AGENTS.md, `config.toml.example`, `tech-stack.md` and the superseded ADR rows agree, but one place still contradicts it: `.env.example` line 6 still has `BOOKSAVER_LLM_API_KEY=` (unused in `src`; a local deny rule blocks reading or editing `.env*`). ADR-019 was still `accepted` for personal Anthropic keys; on 2026-11-10T00:58:36Z its status was amended to record that ADR-063 removed them |
| US-253 | Issues #79 and #3 closed with a summary | ✅ #79 closed 2026-11-10T00:54:03Z (completed), #3 closed 2026-11-10T00:54:04Z (not planned), each with a summary of intent 030 |

Caveat: Daemon logs from the promotion to 2026-11-10T00:41Z no longer exist (another session recreated the container at 00:41:38Z), so "no errors" rests on database outcomes and the later promotion health logs.

The bolt stays open until the remaining US-253 contradiction is fixed: the owner removes the
`.env.example` line. ADR-019's status now records that ADR-063 retired personal Anthropic keys.
