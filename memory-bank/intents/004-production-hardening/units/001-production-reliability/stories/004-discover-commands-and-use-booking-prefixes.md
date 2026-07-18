---
id: 004-discover-commands-and-use-booking-prefixes
unit: 001-production-reliability
intent: 004-production-hardening
status: ready
priority: must
created: 2026-07-18T17:48:48Z
assigned_bolt: 013-production-reliability
implemented: false
---

# Story: Discover Commands and Use Booking Prefixes

**Global story ID**: US-040

## User Story

**As an** authorized Telegram user
**I want** the bot to show every supported command and accept the booking identifier it displays
**So that** I can register and inspect bookings without guessing commands or copying a hidden full UUID

## Acceptance Criteria

- [ ] **Given** an authorized user sends `/start`, **When** the bot responds, **Then** it sends a
  welcome message followed by the complete command reference.
- [ ] **Given** a user sends `/help`, **When** the command reference is rendered, **Then** it includes
  `/register`, `/setkey`, `/deletekey`, and `/admin` alongside existing commands.
- [ ] **Given** `/status` or `/bookings` displays an eight-character booking prefix, **When** the user
  sends `/checks <prefix>`, **Then** a unique caller-owned booking resolves successfully.
- [ ] **Given** a reference is shorter than eight characters, ambiguous, nonexistent, or belongs only
  to another user, **When** `/checks` resolves it, **Then** the same non-disclosing not-found response
  is returned.
- [ ] **Given** the full caller-owned UUID is provided, **When** `/checks` resolves it, **Then** existing
  behavior remains unchanged.

## Technical Notes

- Resolve prefixes only over the caller-scoped booking collection returned by the repository port.
- Require uniqueness after filtering by caller; do not probe global booking existence.
- Keep `/admin` authorization enforcement unchanged even though the command is discoverable.

## Dependencies

### Requires

- Intent 003 user-scoped Telegram command routing and repositories.

### Enables

- A self-explanatory operational flow from registration through check inspection.

## Edge Cases

| Scenario | Expected Behavior |
|----------|-------------------|
| Two caller-owned UUIDs share the same eight-character prefix | Return not found/ambiguous without choosing one |
| Another user owns the only global match | Return the same not-found response |
| Uppercase UUID characters | Preserve existing exact-ID normalization behavior; no extra global lookup |

## Out of Scope

- Adding new Telegram operations or changing access roles.
- Fuzzy property-name lookup for `/checks`.
- Revealing whether another user owns a supplied identifier.
