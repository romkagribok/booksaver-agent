---
id: 002-show-secret-safe-api-key-provenance
unit: 007-shared-browser-use-access
intent: 023-replaceable-agentic-browser-executor
status: complete
priority: must
created: 2026-09-03T23:30:00.000Z
assigned_bolt: 065-shared-browser-use-access
implemented: true
---

# Story: Show Secret-Safe API-Key Provenance

## User Story

**As a** deployment owner
**I want** `/admin users` to show which funding policy applies to each user
**So that** I can understand who consumes my Browser Use API budget without exposing anyone's key

## Acceptance Criteria

- [x] Every admin user row states that Browser Use is funded by the deployment owner.
- [x] Every row states whether a personal legacy key is configured using only a boolean-derived
  `configured` or `not configured` label.
- [x] The aggregate repository never decrypts or returns plaintext, ciphertext, key fragments,
  hashes, fingerprints, or validation results.
- [x] Telegram output remains owner-only, excludes exact user domain records, and retains funding
  visibility when runtime usage counters are unavailable.
- [x] Tests seed recognizable secret sentinels and prove none appear in projections or replies.
- [x] No historical attempt is attributed to a key source that was not persisted with that attempt.

## Dependencies

- US-069, US-146, ADR-019, ADR-036, and ADR-043.
