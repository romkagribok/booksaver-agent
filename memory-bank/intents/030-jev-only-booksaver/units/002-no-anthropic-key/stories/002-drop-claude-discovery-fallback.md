---
id: 002-drop-claude-discovery-fallback
unit: 002-no-anthropic-key
intent: 030-jev-only-booksaver
status: draft
priority: must
created: "2026-11-04T16:13:23Z"
assigned_bolt: 099-no-anthropic-key
implemented: false
---

# US-247: Drop the Claude discovery fallback

## User story

As the owner, I want discovery to need no Claude, so that the Anthropic key can go.

## Assigned requirement

FR-9.

## Acceptance criteria

- [ ] Given a trip list the code reader cannot read, when syncing, then the sync fails visibly and no model navigates.
- [ ] Given an account the code reader reads, when syncing, then the result is unchanged.

## Out of scope

Anything outside unit 002-no-anthropic-key.
