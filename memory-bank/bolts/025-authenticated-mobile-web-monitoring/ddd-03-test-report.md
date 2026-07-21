---
stage: test
bolt: 025-authenticated-mobile-web-monitoring
created: 2026-07-19T21:53:34Z
---

# Test Report: Authenticated Mobile-Web Monitoring

## Summary

- **Full regression**: 836/836 tests passed.
- **Mobile configuration/context/provenance checks**: 22/22 focused tests passed in the initial
  slice; authenticated monitor, coordinator, persistence, Telegram, alert, and handoff cases were
  added and passed in the integrated suite.
- **Static quality**: Ruff passed for `src/` and `tests/`; mypy passed for all 85 source files.
- **Coverage**: not measured because `pytest-cov` is not installed in the repository toolchain.
- **Request-path/performance posture**: no extra Booking.com journey was introduced; checks remain
  serialized and use the existing hard step/LLM/time budgets.

## Acceptance Criteria Validation

- ✅ **US-083**: every production browser factory uses a fresh allowlisted Playwright Android
  Chromium descriptor with mobile UA, viewport/screen, touch, scale, locale, and timezone; desktop
  or unknown aliases fail config validation.
- ✅ **US-084**: the coordinator restores exactly one immutable owner revision into that fresh
  context, and missing/revoked/foreign state produces no navigation or accepted price.
- ✅ **US-085**: rendered authentication requires positive account/Genius evidence; signed-out or
  ambiguous pages fail closed, while authenticated pages may validly record Genius `not_observed`.
- ✅ **US-086**: trusted results URL, exact property/context verification, semantic offer parsing,
  currency recovery, equivalence/refundability gates, bounded LLM escalation, and the action guard
  remain on the same monitor path.
- ✅ **US-087**: every accepted authenticated-mobile price carries channel/profile/revision/auth/
  Genius/timestamp provenance through schema v10 history, trace, `/checks`, `/checknow`, and alerts.
- ✅ **US-088**: rebook handoff directs the user to a real phone, the same signed-in Booking.com
  account, and verification of final all-in total and refundability; native-app/app-only rates are
  explicitly outside the claim.

## Migration and Compatibility

- Schema v9→v10 adds six nullable provenance columns without losing prior history; legacy rows load
  with no source value.
- Existing non-provenance rendering remains compatible, while daemon-produced accepted prices use
  complete authenticated-mobile provenance.
- Playwright device descriptors come from the installed Playwright build, preventing a stale
  hard-coded Chrome user agent from diverging from bundled Chromium.

## Issues Found and Resolved

- Negative-only authentication detection could treat an ambiguous page as signed in; accepted
  prices now require positive rendered evidence.
- An early profile draft hard-coded a browser version; it now uses Playwright's version-matched
  `Pixel 7`/`Pixel 5` descriptors.
- Six older migration assertions expected schema v9; they were updated to verify v10 progression.

## Review Gate

Implementation and Test are complete. Bolt status intentionally remains `in-progress`; story flags,
completion cascade, commit, push, and deployment await product-owner approval.
