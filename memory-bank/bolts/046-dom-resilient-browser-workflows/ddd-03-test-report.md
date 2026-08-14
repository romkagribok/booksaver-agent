---
unit: 002-dom-resilient-browser-workflows
bolt: 046-dom-resilient-browser-workflows
stage: test
status: complete
updated: 2026-08-14T03:21:03Z
---

# Test Report - Atomic Remote-Authentication Finalization

## Outcome

A code-verified Booking.com login now enters an explicit `finalizing` phase before the browser
runner returns. Ordinary viewer close and replacement attempts cannot cancel that phase; the
application manager waits for browser cleanup, commits the encrypted session, publishes pending
recovery evidence, exposes success, notifies Telegram, and only then permits the Mini App to close.

Capture rejection remains fail-closed and drops pending recovered evidence. Administrative
user-scoped cancellation and daemon shutdown retain authority over a finalizing attempt before
capture begins.

## Verification Summary

| Gate | Result |
|---|---:|
| Remote-auth manager, runner, gateway, and real viewer-browser focused set | 63 passed |
| Remote-auth deployment plus Telegram purge/gateway regression set | 55 passed |
| Full repository suite | 1548 passed |
| Ruff across `src` and `tests` | Passed |
| Strict mypy across `src` (117 files) | Passed |
| CLI help smoke | Passed |
| AI-DLC artifact and status-integrity validators | Passed; 0 issues/inconsistencies |
| Diff whitespace validation | Passed |

The full suite emitted only the existing `schedule.check_interval` deprecation warnings.

## Acceptance Criteria Validation

- ✅ A fresh code-owned authenticated-inventory proof must acquire the manager's finalization latch
  before any runner success can be persisted.
- ✅ `finalizing` is visible without WebSocket authority; viewer controls and cancel are disabled,
  RFB disconnects, polling continues, and pagehide cancellation is suppressed.
- ✅ Server-side viewer cancellation and same-user replacement are refused during finalization even
  if the Mini App closes before observing the new state.
- ✅ Administrative cancellation during the post-verification/pre-capture window still wins and
  produces no encrypted session.
- ✅ Browser/context/display cleanup still happens before the runner returns pending cookies and
  sanitized evidence to the manager.
- ✅ Encrypted capture precedes recovered-incident publication, terminal success, post-connect
  synchronization, Telegram notification, and success-only Mini App close.
- ✅ Capture rejection produces `CAPTURE_REJECTED`, specific safe retry guidance, no recovered
  incident, no success callback, and logs only the exception class.
- ✅ Incident persistence failure is isolated after session capture and cannot undo committed
  success; neither incident details nor exception messages enter ordinary logs.
- ✅ A runner that returns cookies without finalization admission is rejected and cannot save a
  session.
- ✅ Failed, expired, and cancelled terminal states remain visible and never auto-close Telegram.

## Release Follow-up

This bolt is code-complete and not deployed. The next checkpoint is owner review of the branch/PR.
After approval, merge and deploy through the operations flow, then perform human `/connect`
acceptance before `/status`, `/bookings`, and `/checknow` as applicable.
