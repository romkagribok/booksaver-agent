---
id: 002-bind-owner-authenticated-session
unit: 001-authenticated-mobile-web-monitoring
intent: 013-authenticated-mobile-web-monitoring
status: complete
priority: must
created: 2026-07-19T21:23:00.000Z
assigned_bolt: 025-authenticated-mobile-web-monitoring
implemented: true
---
# Story: Bind Each Check to Its Owner's Authenticated Session
**Global story ID**: US-084

As a user, I want my mobile check bound to my session revision so that account eligibility and privacy remain correct.

## Acceptance Criteria
- [ ] Owner/access/session are revalidated before browser navigation.
- [ ] Missing/revoked/foreign/replaced state yields no navigation, price, or fallback.
