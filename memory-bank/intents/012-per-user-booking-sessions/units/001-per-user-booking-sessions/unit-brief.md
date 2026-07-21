---
unit: 001-per-user-booking-sessions
intent: 012-per-user-booking-sessions
phase: construction
status: complete
unit_type: cli
default_bolt_type: ddd-construction-bolt
created: 2026-07-19T21:23:00.000Z
updated: 2026-07-19T21:53:34.000Z
---

# Unit Brief: Per-User Booking.com Sessions

## Purpose

Provide a fail-closed, encrypted, user-isolated authenticated browser-state capability for every
scheduled and Telegram-triggered Booking.com check.

## Scope and Operations

- Import/replace/delete/status by admitted Telegram ID through the local CLI.
- Encrypt/decrypt an immutable user-owned session revision.
- Resolve one active booking owner's session and restore it only into a clean context.
- Mark/refresh a revision safely after rendered authentication validation.
- Report missing/expired/invalid state without secrets or cross-user metadata.

## Assigned Requirements

FR-1, FR-2, FR-3, FR-4, FR-5, and FR-6.

## Story Summary

| Story | Title | Priority | Status |
|-------|-------|----------|--------|
| US-077 | Isolate Booking.com sessions by user | Must | Ready |
| US-078 | Import a user session securely | Must | Ready |
| US-079 | Protect user session at rest | Must | Ready |
| US-080 | Inspect session health safely | Must | Ready |
| US-081 | Enforce authenticated check policy | Must | Ready |
| US-082 | Preserve session safety and lifecycle | Must | Ready |

## Success Criteria

- No global/foreign/public fallback and no browser-state bleed.
- Auth failures are user-scoped, actionable, and savings-suppressing.
- Stored state is encrypted and logs/output remain redacted.
- Full quality gates pass without autonomous booking behavior.
