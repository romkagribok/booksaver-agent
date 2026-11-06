---
id: 001-drop-claude-tables
unit: 004-claude-data-config-docs
intent: 030-jev-only-booksaver
status: draft
priority: must
created: "2026-11-04T16:13:23Z"
assigned_bolt: 101-claude-data-config-docs
implemented: false
---

# US-251: Drop the Claude tables

## User story

As the owner, I want no dead Claude data, so that the schema is honest.

## Assigned requirement

FR-13.

## Acceptance criteria

- [ ] Given a backup, when the migration runs, then the three Claude tables are gone and personal keys are cleared.

## Out of scope

Anything outside unit 004-claude-data-config-docs.
