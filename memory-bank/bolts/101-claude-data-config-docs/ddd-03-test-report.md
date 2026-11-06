---
unit: 004-claude-data-config-docs
bolt: 101-claude-data-config-docs
stage: test
status: complete
created: 2026-11-06T03:03:29Z
updated: 2026-11-06T03:03:29Z
---

# Test Report - Claude Data, Config and Docs

Covered by the bolt 100 step 2 run: production config loads with one warning listing the retired
keys; a config without them warns nothing; the v24 migration drops the tables and clears keys on
cloned production data (schema 24, no `llm_` tables, no personal keys).

Not done: `.env.example` still names `BOOKSAVER_LLM_API_KEY`; a local deny rule prevents reading or
editing `.env*` files. The owner is asked to remove that line.
