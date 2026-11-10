---
id: 002-delete-claude-only-code
unit: 003-delete-claude-code
intent: 030-jev-only-booksaver
status: complete
priority: must
created: "2026-11-04T16:13:23Z"
assigned_bolt: 100-delete-claude-code
implemented: true
---

# US-250: Delete the Claude-only code

## User story

As the owner, I want the Claude code gone, so that there is less to maintain.

## Assigned requirement

FR-11, FR-12.

## Acceptance criteria

- [x] Given the source tree, when searched, then no module imports anthropic or stagehand.
- [x] Given the full suite and a live replay, when run, then behaviour matches unit 2.

## Out of scope

Anything outside unit 003-delete-claude-code.
