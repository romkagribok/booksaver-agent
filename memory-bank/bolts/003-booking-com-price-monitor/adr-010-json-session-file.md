---
unit: 002-booking-com-price-monitor
bolt: 003-booking-com-price-monitor
id: ADR-010
title: JSON file (not SQLite) for Booking.com session cookies
status: accepted
updated: 2026-07-05T00:00:00Z
---

# ADR-010: JSON file for session cookie storage

## Context

US-004 requires the Booking.com session to be persisted locally and reused. The obvious
home for persistent data is the existing SQLite store (ADR-001). Alternative: a standalone
JSON file in the data directory.

## Decision

Store session state as **`{data_directory}/session_booking_com.json`** (mode `0600`),
containing Playwright's native cookies array plus session metadata
(`authenticated_at`, `expires_at`, `status`).

## Rationale

- Playwright natively imports/exports cookies as JSON (`context.cookies()` /
  `add_cookies()`); storing the same shape avoids a serialise-to-SQL round trip that adds
  code but no integrity benefit.
- Session state is a single mutable blob with no relational structure, no invariants that
  SQL constraints could enforce, and no queries beyond load/save.
- A separate file makes "log out / reset session" trivially explainable to the user:
  delete one file. It also keeps volatile auth material out of the durable booking DB.

## Consequences

- `SessionRepository` port has a file-based adapter (`LocalSessionRepository`); tests use
  a tmp dir, no DB fixtures needed.
- File permissions `0600` enforced on every save (matches DB hardening from Bolt 001).
- If Unit 4 (guided rebook) or a second platform (Unit 5) needs sessions, the same
  file-per-platform pattern extends naturally (`session_{platform}.json`).
