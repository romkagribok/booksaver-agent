---
id: 004-capture-and-teardown-session
unit: 002-remote-authentication-gateway
intent: 012-per-user-booking-sessions
status: complete
priority: must
created: 2026-07-20T02:25:00.000Z
assigned_bolt: 026-remote-authentication-gateway
implemented: true
---
# Story: Capture Authenticated State and Tear Down
**Global story ID**: US-092

As a user, I want successful login to become my encrypted BookSaver session and all temporary login machinery to disappear afterward.

## Acceptance Criteria
- [ ] Positive rendered authentication and active admission are rechecked before capture.
- [ ] Booking.com cookies pass the existing normalization boundary and atomically replace only the caller's revision.
- [ ] Every terminal path stops browser/VNC/display/proxy processes and removes transient credentials.
