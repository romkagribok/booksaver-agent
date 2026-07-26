---
intent: 015-authentication-boundary-hardening
phase: inception
status: units-decomposed
updated: 2026-07-26T19:41:07Z
---

# Authentication Boundary Hardening - Unit Decomposition

## Units Overview

### Unit 1: `001-complete-user-purge`

**Description**: Coordinate remote-auth cancellation, permanent encrypted-session revocation, and
existing database purge semantics for both Telegram admin confirmation paths.

**Assigned Requirements**: FR-1.

**Dependencies**: Completed user access, per-user Booking.com sessions, and remote-auth manager.

### Unit 2: `002-direct-booking-auth-only`

**Description**: Enforce a Booking.com-only document-navigation boundary across main pages, child
frames, and popups, and tell users to use direct credentials before and during `/connect`.

**Assigned Requirements**: FR-2, FR-3.

**Dependencies**: Completed remote-auth browser runner, Telegram `/connect`, and viewer status.

## Requirement-to-Unit Mapping

- **FR-1** → `001-complete-user-purge`
- **FR-2** → `002-direct-booking-auth-only`
- **FR-3** → `002-direct-booking-auth-only`

## Execution Order

The units are independent and may be constructed in parallel. Both must complete before the
authentication-boundary hardening release is deployable.
