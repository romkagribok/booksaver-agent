---
id: 001-block-external-provider-navigation
unit: 002-direct-booking-auth-only
intent: 015-authentication-boundary-hardening
status: complete
priority: must
created: 2026-07-26T19:41:07.000Z
assigned_bolt: 029-direct-booking-auth-only
implemented: true
---

# Story: Block External Identity-Provider Navigation

## User Story

**As a** Telegram BookSaver user
**I want** the remote login browser restricted to Booking.com pages
**So that** I cannot enter credentials into an unsupported external provider flow

## Acceptance Criteria

- [ ] **Given** an exact Booking.com host or subdomain, **When** a top-level page navigates, **Then**
  navigation continues.
- [ ] **Given** any external provider or arbitrary host, **When** a main page, child frame, or popup
  navigates, **Then** the request is aborted with `blockedbyclient`.
- [ ] **Given** a lookalike host such as `booking.com.attacker.example`, **When** it navigates,
  **Then** it is blocked.
- [ ] **Given** Booking.com requests external scripts, images, or other non-navigation resources,
  **When** they load, **Then** the existing resource behavior is preserved.

## Technical Notes

- Replace the multi-host top-level allowlist with a Booking.com-specific host predicate.
- Context-level routing is installed before `new_page()` and therefore covers popups.

## Dependencies

### Requires

- Existing remote browser runner security route.

### Enables

- US-100 direct-login guidance.

## Edge Cases

| Scenario | Expected Behavior |
|----------|-------------------|
| User pastes an external URL | Top-level request blocked |
| Provider opens a new window or child frame | External document request blocked |
| External script is required by Booking.com | Subresource continues |

## Out of Scope

- A total network allowlist or provider-specific DOM modification.
