---
stage: test
bolt: 029-direct-booking-auth-only
created: 2026-07-26T21:23:28Z
---

## Test Report: Direct Booking Authentication Only

### Summary

- **Focused tests**: 92/92 passed across the integrated purge and remote-auth boundary
- **Full tests**: 883/883 passed
- **Ruff**: Clean across `src` and `tests`
- **mypy**: Clean across 93 source files
- **AI-DLC artifact validator**: 0 issues
- **AI-DLC status integrity**: 0 inconsistencies after the deterministic construction-state repair
- **Diff hygiene**: Clean

### Test Files

- [x] `tests/unit/test_remote_browser_runner.py` - Exact/subdomain Booking hosts, external
  providers, arbitrary and lookalike hosts, popup coverage, and preserved external resources.
- [x] `tests/unit/telegram/test_connect_command.py` - Typed and callback launch guidance.
- [x] `tests/unit/test_remote_auth.py` - Ready and connected viewer guidance.
- [x] `tests/unit/test_remote_auth_gateway.py` - Existing viewer security and response boundaries.
- [x] Full `tests/` suite - Cross-component regression.

### Acceptance Criteria Validation

- ✅ **Allow Booking.com navigation**: Exact `booking.com` and dot-delimited subdomains continue.
- ✅ **Block provider and arbitrary navigation**: Google, Apple, Microsoft, Facebook, arbitrary
  external hosts, child-frame documents, and popup documents abort with `blockedbyclient`.
- ✅ **Reject lookalikes**: Suffix tricks such as `booking.com.attacker.example` do not match.
- ✅ **Preserve required resources**: External scripts, images, and other non-navigation requests
  retain the existing continue behavior.
- ✅ **Guide before launch**: Typed and callback `/connect` messages require Booking.com
  email/password, say providers are disabled, and warn never to send a password in Telegram.
- ✅ **Guide inside the viewer**: Ready and connected states repeat the direct-login-only message
  without exposing runtime secrets.

### Issues Found

- Status integrity found the new intent still marked `units-defined` after construction began. The
  framework's deterministic `--fix` path aligned it to `construction` and logged the repair.
- Independent review found that top-level-only enforcement still permitted an external provider
  document inside a child frame. The final policy blocks every external navigation request while
  preserving ordinary cross-origin subresources.

### Remaining Acceptance

Provider buttons intentionally remain visible because Booking.com DOM selectors are outside this
stable security boundary; clicking one is blocked at navigation. A deployed Telegram mobile and
desktop `/connect` test must confirm the direct Booking.com credential path still completes.
