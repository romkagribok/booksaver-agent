---
stage: implement
bolt: 031-remote-auth-attempt-recovery
created: 2026-07-26T23:01:40Z
---

## Implementation Walkthrough: Remote Authentication Attempt Recovery

### Summary

A new `/connect` from the owner of an active remote-auth attempt now immediately cancels and
replaces that attempt in one command. The manager retains the already-held global browser gate
across teardown and hands it directly to the replacement, so a scheduled price check or another
login cannot enter between the two workers.

### Completed Work

- [x] `src/booksaver/application/remote_auth.py` - Serializes creation, verifies active-attempt
  ownership, cancels same-user attempts, waits outside the manager lock, transfers a reserved
  browser gate, handles bounded timeout, and suppresses the replaced attempt's redundant
  cancellation notification.
- [x] `src/booksaver/infrastructure/remote_auth/viewer.py` - Sends one authenticated best-effort
  cancellation on non-bfcache `pagehide`, while explicit Cancel remains awaited and terminal states
  suppress close cancellation.
- [x] `tests/unit/test_remote_auth.py` - Covers immediate replacement, old-capability isolation,
  terminal-but-tearing-down replacement, gate reservation, teardown timeout, cross-user denial, and
  two racing same-user commands.
- [x] `tests/integration/test_remote_auth_viewer_browser.py` - Proves pagehide cancellation is sent
  and visibility-only changes do not cancel.

### Key Decisions

- **Latest same-user request wins**: No heartbeat or stale grace delays recovery after a lost viewer.
- **Reserve the existing lease**: The old worker clears active state but deliberately retains the
  browser gate for the matching replacement.
- **Never join under the manager lock**: Worker cleanup and capture/cancel serialization cannot
  deadlock.
- **Fail closed on slow teardown**: The attempt remains single-browser and the user receives
  specific short retry guidance.
- **Keep close best-effort**: WebView lifecycle delivery improves responsiveness but is not the
  correctness boundary.

### Deviations from Plan

None.

### Dependencies Added

None.
