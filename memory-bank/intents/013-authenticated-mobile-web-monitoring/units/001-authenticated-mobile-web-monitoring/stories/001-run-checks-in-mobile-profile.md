---
id: 001-run-checks-in-mobile-profile
unit: 001-authenticated-mobile-web-monitoring
intent: 013-authenticated-mobile-web-monitoring
status: complete
priority: must
created: 2026-07-19T21:23:00.000Z
assigned_bolt: 025-authenticated-mobile-web-monitoring
implemented: true
---
# Story: Run Every Check in a Configured Mobile-Web Profile
**Global story ID**: US-083

As a user, I want checks to render the mobile website so that mobile-web rates can be considered.

## Acceptance Criteria
- [ ] One allowlisted profile configures UA, viewport/screen, touch, scale, locale/timezone, and mobile behavior.
- [ ] Android-like Chromium is the VPS default; unknown/desktop profiles fail validation.
- [ ] A fresh deterministic context is created for each session boundary.
