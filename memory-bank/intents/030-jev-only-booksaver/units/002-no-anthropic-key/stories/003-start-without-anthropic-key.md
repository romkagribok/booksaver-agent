---
id: 003-start-without-anthropic-key
unit: 002-no-anthropic-key
intent: 030-jev-only-booksaver
status: draft
priority: must
created: "2026-11-04T16:13:23Z"
assigned_bolt: 099-no-anthropic-key
implemented: false
---

# US-248: Start without the Anthropic key

## User story

As the owner, I want BookSaver to run with no Anthropic key, so that I can revoke it.

## Assigned requirement

FR-10.

## Acceptance criteria

- [ ] Given BOOKSAVER_LLM_API_KEY unset, when the daemon starts, then the bot, syncs and Jev price checks run.
- [ ] Given the release on the VPS, when verified, then the key is removed from the environment and the owner is asked to revoke it.

## Out of scope

Anything outside unit 002-no-anthropic-key.
