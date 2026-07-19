---
id: 005-preserve-access-and-visible-completion
unit: 001-post-rebook-monitoring
intent: 011-post-rebook-monitoring
status: complete
priority: must
created: 2026-07-19T19:50:29.000Z
assigned_bolt: 023-post-rebook-monitoring
implemented: true
---

# Story: Preserve Access and Visible Completion

**Global story ID**: US-076

## User Story

**As an** authorized booking owner
**I want** every answer and final monitoring disposition confirmed privately
**So that** I know what BookSaver will check and nobody else can change it

## Acceptance Criteria

- [ ] Active access and ownership are rechecked before prompts and inside mutation.
- [ ] Revocation, foreign/stale input, and guessed identifiers cause no mutation or disclosure.
- [ ] Accepted detail answers are visible and every terminal path states the monitored disposition.
- [ ] Existing private-chat and callback protections remain effective.

## Dependencies

- Intent 010 privacy boundaries and US-072 through US-075.
