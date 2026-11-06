---
unit: 004-claude-data-config-docs
bolt: 101-claude-data-config-docs
stage: design
status: complete
created: 2026-11-06T03:03:29Z
updated: 2026-11-06T03:03:29Z
---

# Technical Design - Claude Data, Config and Docs

Implemented together with bolt 100 step 2 in one change, because the configuration fields and
tables belonged to the code being deleted. These documents were written after that code, from the
approved requirements (FR-13 to FR-15).

- Schema v24: drop `llm_spend_days`, `llm_cost_reservations`, `llm_profile_qualifications`; clear
  `users.encrypted_key` (column kept). Idempotent; tested from v23 and v13.
- `load_config`: retired keys (Claude models, model-call limits, agent step and recovery settings,
  `[extraction]`, `routing`, `inventory_routing`) are ignored with one `UserWarning` naming them.
- Docs: README, AGENTS.md (secrets), config.toml.example, docker-compose.yml, the systemd unit and
  the standards; ADR-063.
- Deploy: retired keys are removed from the production config so it loads without the warning.
