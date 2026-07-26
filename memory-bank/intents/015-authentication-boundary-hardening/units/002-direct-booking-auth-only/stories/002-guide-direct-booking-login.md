---
id: 002-guide-direct-booking-login
unit: 002-direct-booking-auth-only
intent: 015-authentication-boundary-hardening
status: complete
priority: must
created: 2026-07-26T19:41:07.000Z
assigned_bolt: 029-direct-booking-auth-only
implemented: true
---

# Story: Guide Users to Direct Booking.com Login

## User Story

**As a** Telegram BookSaver user
**I want** to know the supported sign-in method before opening `/connect`
**So that** I do not choose a provider flow that the remote browser blocks

## Acceptance Criteria

- [ ] **Given** I request `/connect`, **When** the launch control appears, **Then** its message tells
  me to use Booking.com email/password and says external providers are disabled.
- [ ] **Given** the remote browser is ready or connected, **When** I view its status, **Then** the
  same direct-login-only guidance remains visible.
- [ ] **Given** the guidance is inspected, **When** sensitive-data boundaries are evaluated,
  **Then** it states that BookSaver never asks for passwords in Telegram and exposes no runtime
  secrets.

## Technical Notes

- Update stable BookSaver-owned text rather than injecting selectors into Booking.com's layout.
- Keep terminal success/failure/cancel/expiry messages unchanged.

## Dependencies

### Requires

- US-099 provider navigation blocking.

### Enables

- Real Telegram acceptance of the supported login path.

## Edge Cases

| Scenario | Expected Behavior |
|----------|-------------------|
| Booking.com changes provider buttons | Guidance and network boundary remain intact |
| User opens `/connect` from a reconnect callback | The same launch guidance is shown |

## Out of Scope

- Creating or resetting a Booking.com password for the user.
