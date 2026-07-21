---
id: 003-protect-user-session-at-rest
unit: 001-per-user-booking-sessions
intent: 012-per-user-booking-sessions
status: complete
priority: must
created: 2026-07-19T21:23:00.000Z
assigned_bolt: 024-per-user-booking-sessions
implemented: true
---
# Story: Protect User Session at Rest
**Global story ID**: US-079

As a user, I want my Booking.com browser state encrypted on the owner-operated host so that a copied data file is not directly usable.

## Acceptance Criteria
- [ ] Fernet protects every per-user bundle and files are atomically written with restrictive permissions.
- [ ] Key errors fail closed and never overwrite a valid bundle.
- [ ] Legacy global state requires explicit owner migration and is never shared implicitly.
