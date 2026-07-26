---
stage: test
bolt: 031-remote-auth-attempt-recovery
created: 2026-07-26T23:02:46Z
---

## Test Report: Remote Authentication Attempt Recovery

### Summary

- **Focused remote-auth/deployment/browser tests**: 36/36 passed
- **Full tests**: 898/898 passed
- **Ruff**: Clean across `src` and `tests`
- **mypy**: Clean across 94 source files

### Acceptance Criteria Validation

- ✅ **Best-effort close detection**: Non-bfcache `pagehide` sends one same-origin, cookie-authenticated
  keepalive cancellation; visibility changes do not cancel.
- ✅ **Immediate correctness fallback**: A new same-user `/connect` cancels the current attempt
  without a heartbeat or wait-for-stale requirement.
- ✅ **Single-command replacement**: Normal worker teardown returns a fresh login link from that
  same command.
- ✅ **Single global browser**: A reserved gate remains locked throughout teardown and replacement.
- ✅ **Bounded failure**: Slow teardown starts no replacement and produces specific short retry
  guidance; later worker cleanup releases the gate once.
- ✅ **Cross-user privacy**: Another user receives the existing generic busy response and cannot
  cancel or inspect the active attempt.
- ✅ **Capability isolation**: The old viewer token remains terminal and cannot cancel or change the
  replacement.
- ✅ **Repeated commands**: Two same-user replacements serialize; the latest wins and only one
  browser remains active.
- ✅ **Capture/cancel boundary**: Existing critical-section tests remain green, preserving either
  captured success or cancellation, never both.

### Remaining Acceptance

Live Telegram verification must cover closing the viewer by swipe/window close and immediately
sending `/connect` again on Android, iOS, and Desktop. This is a production acceptance gate because
WebView close delivery cannot be guaranteed by headless browser automation; manager-side recovery
is already independent of that delivery.
