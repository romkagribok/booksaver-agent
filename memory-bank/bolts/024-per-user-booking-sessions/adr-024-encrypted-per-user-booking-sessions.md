---
adr: ADR-024
status: accepted
created: 2026-07-19T21:23:00Z
bolt: 024-per-user-booking-sessions
amends: ADR-010
---

# ADR-024: Encrypted Per-User Booking.com Sessions

## Context

ADR-010 chose one 0600 JSON/base64 session file. Telegram sharing and Genius monitoring make that
global state unsafe and public fallback misleading.

## Decision

Store one Fernet-encrypted, versioned Booking.com browser-state bundle per stable local user ID outside
SQLite. Resolve it only after booking ownership and active access checks, restore it into a clean
browser context, and fail closed for Telegram-owned checks when authentication cannot be proven.
Cookie import remains an owner-operated CLI/SCP procedure; Telegram never transports the payload.

## Consequences

- Cross-user isolation and at-rest confidentiality improve substantially.
- Operators must configure the encryption secret and refresh each user's cookies when required.
- ADR-010's global file remains only as an explicit owner migration source, not a runtime fallback.
- Public prices remain a separately labeled local-only mode, never an authenticated Telegram result.
