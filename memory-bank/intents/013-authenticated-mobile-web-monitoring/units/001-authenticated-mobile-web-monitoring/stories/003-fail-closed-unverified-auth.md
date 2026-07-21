---
id: 003-fail-closed-unverified-auth
unit: 001-authenticated-mobile-web-monitoring
intent: 013-authenticated-mobile-web-monitoring
status: complete
priority: must
created: 2026-07-19T21:23:00.000Z
assigned_bolt: 025-authenticated-mobile-web-monitoring
implemented: true
---
# Story: Fail Closed When Authenticated Context Is Unverified
**Global story ID**: US-085

As a user, I want BookSaver to prove my login context so that a public/ambiguous price is never mislabeled as Genius-capable.

## Acceptance Criteria
- [ ] Signed-out/indeterminate authentication fails closed and invalidates the exact revision safely.
- [ ] Genius evidence is present, not observed, or indeterminate; only evidence supports a Genius claim.
- [ ] Authenticated plus not-observed remains a valid price source.
