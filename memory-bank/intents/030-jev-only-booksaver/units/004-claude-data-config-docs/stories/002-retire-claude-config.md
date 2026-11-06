---
id: 002-retire-claude-config
unit: 004-claude-data-config-docs
intent: 030-jev-only-booksaver
status: draft
priority: must
created: "2026-11-04T16:13:23Z"
assigned_bolt: 101-claude-data-config-docs
implemented: false
---

# US-252: Retire the Claude config keys

## User story

As the owner, I want old configs to keep loading, so that upgrades are safe.

## Assigned requirement

FR-14.

## Acceptance criteria

- [ ] Given a config with Claude model keys, when loaded, then one warning is logged and it loads.

## Out of scope

Anything outside unit 004-claude-data-config-docs.
