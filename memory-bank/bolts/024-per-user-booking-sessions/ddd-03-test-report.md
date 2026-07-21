---
stage: test
bolt: 024-per-user-booking-sessions
created: 2026-07-19T21:53:34Z
---

# Test Report: Per-User Booking.com Sessions

## Summary

- **Full regression**: 836/836 tests passed.
- **Focused session/coordinator/monitor/persistence verification**: 60/60 tests passed before the
  final integrated run, with additional coordinator and authentication-evidence cases added after.
- **Static quality**: Ruff passed for `src/` and `tests/`; mypy passed for all 85 source files.
- **Coverage**: not measured because this repository does not install `pytest-cov`; acceptance
  behavior is covered directly by unit and integration tests.
- **Performance**: no synthetic benchmark added. The existing serialized browser gate remains, and
  unavailable sessions exit before navigation or LLM work.

## Acceptance Criteria Validation

- ✅ **US-077**: booking ownership resolves a stable local user ID; scheduled checks use a new
  browser context per booking; no global/owner/public fallback is reachable from the coordinator.
- ✅ **US-078**: scoped CLI import rejects unknown/revoked users and malformed, foreign-domain, or
  expired exports; output is redacted and the runbook requires SSH/SCP rather than Telegram upload.
- ✅ **US-079**: normalized cookies are Fernet-encrypted per user, written atomically with 0700/0600
  permissions, protected from wrong-key overwrite, and legacy state requires explicit owner migration.
- ✅ **US-080**: CLI and Telegram status expose only health/timestamps plus a Telegram-ID-scoped
  re-import command; cookies and account identifiers are absent.
- ✅ **US-081**: missing/expired/invalid/signed-out state records `auth_required`, creates history and
  trace, suppresses savings, and marks only the resolved revision for reauthentication.
- ✅ **US-082**: refresh and invalidation are owner/revision guarded under a per-owner file lock;
  revocation blocks resolution/refresh; targeted deletion and the human-only action boundary remain.

## Security and Reliability Cases

- Restore exceptions are redacted before history, trace, and Telegram output.
- Sequential scheduled checks prove distinct browser objects; owner/invitee resolution and revoked
  access are tested.
- Scheduled and on-demand paths both report scoped `auth_required`; one user's missing session does
  not prevent a later user's ready session from running in the same scheduled batch.
- Stale revision compare-and-replace is rejected without overwriting a newer import.
- A valid encrypted bundle survives malformed input and missing/wrong Fernet keys.

## Issues Found and Resolved

- Mixed expired and valid cookie exports previously inherited a past aggregate expiry; already
  expired cookies are now discarded before encrypted persistence.
- Revision compare-and-replace initially had a read/write race; a per-owner filesystem lock now
  makes revision validation and replacement atomic.
- Session-restore exception text initially reached the failure detail; it is now generic and redacted.

## Review Gate

Implementation and Test are complete. Bolt status intentionally remains `in-progress`; story flags,
completion cascade, commit, push, and deployment await product-owner approval.
