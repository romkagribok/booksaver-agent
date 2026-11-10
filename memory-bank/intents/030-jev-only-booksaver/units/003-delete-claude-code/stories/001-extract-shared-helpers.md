---
id: 001-extract-shared-helpers
unit: 003-delete-claude-code
intent: 030-jev-only-booksaver
status: complete
priority: must
created: "2026-11-04T16:13:23Z"
assigned_bolt: 100-delete-claude-code
implemented: true
---

# US-249: Move shared helpers out of Claude modules

## User story

As the owner, I want Jev and the code reader independent of Claude modules, so that those can be deleted.

## Assigned requirement

FR-11.

## Acceptance criteria

- [x] Given Jev and the grouped reader, when imported, then they import nothing from Claude-only modules.

## Out of scope

Anything outside unit 003-delete-claude-code.
