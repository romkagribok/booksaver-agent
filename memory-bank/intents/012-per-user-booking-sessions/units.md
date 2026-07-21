---
intent: 012-per-user-booking-sessions
phase: inception
status: units-decomposed
updated: 2026-07-20T02:25:00Z
---

# Per-User Booking.com Sessions - Unit Decomposition

## Unit 1: `001-per-user-booking-sessions`

One cohesive security boundary owns FR-1 through FR-6: identity binding, encrypted storage,
recovery import, health, authenticated-only resolution, refresh/invalidation, and cross-user proof.

## Unit 2: `002-remote-authentication-gateway`

Owns FR-7 through FR-12: `/connect`, Telegram Mini App identity verification, transient remote mobile
browser orchestration, authenticated capture/teardown, outcome/reconnect messaging, and the opt-in
HTTPS/WSS deployment boundary.

## Requirement-to-Unit Mapping

| Requirement | Unit |
|-------------|------|
| FR-1 through FR-6 | `001-per-user-booking-sessions` |
| FR-7 through FR-12 | `002-remote-authentication-gateway` |

## Dependencies

- Telegram users/bookings and revocation boundaries (bolts 009, 021, 022).
- Existing cookie normalization/session lifecycle (bolt 012; ADR-010 amended here).
- Serialized check coordinator (ADR-021).

## Planned Bolt

- `024-per-user-booking-sessions` — US-077 through US-082.
- `026-remote-authentication-gateway` — US-089 through US-094; requires Bolt 024 and enables final authenticated-mobile review.
