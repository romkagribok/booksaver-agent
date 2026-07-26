---
id: 005-recover-from-abandoned-viewer
unit: 001-device-aware-remote-auth-viewer
intent: 016-device-aware-remote-auth-viewer
status: complete
priority: must
created: 2026-07-26T22:14:47.000Z
assigned_bolt: 031-remote-auth-attempt-recovery
implemented: true
---

# Story: 005-recover-from-abandoned-viewer

## User Story

**As a** Telegram user who accidentally closes the login viewer
**I want** my next `/connect` to reclaim my abandoned attempt safely
**So that** I am not locked out for the entire authentication timeout.

## Acceptance Criteria

- [x] **Given** I press explicit Cancel, **When** the request succeeds or the viewer closes, **Then**
      the existing cancellation event ends the browser and releases the global lease.
- [x] **Given** a conservative Mini App unload signal occurs, **When** the WebView permits
      best-effort delivery, **Then** an authenticated keepalive cancellation is attempted, while
      correctness remains independent of that delivery.
- [x] **Given** Telegram merely backgrounds the Mini App or emits only `visibilitychange`, **Then**
      the attempt is not cancelled solely because visibility changed.
- [x] **Given** my previous attempt is still nonterminal, **When** I request `/connect` again,
      **Then** BookSaver marks only my attempt cancelled under the manager lock and begins bounded
      teardown without requiring a heartbeat or stale timeout.
- [x] **Given** my previous worker releases the browser lease within the bounded teardown window,
      **When** the same `/connect` continues, **Then** BookSaver starts and returns one fresh login
      link immediately.
- [x] **Given** the first reclaim request cancelled my previous attempt, **When** its worker has not
      released the browser lease within the bounded teardown window, **Then** no replacement browser
      starts and I am told to retry shortly.
- [x] **Given** my previous browser is still tearing down, **When** I request `/connect`, **Then** I
      receive a specific short retry instruction rather than “another login is active.”
- [x] **Given** another Telegram user owns the active attempt, **When** I request `/connect`, **Then**
      BookSaver preserves the global single-browser lease and does not cancel, expose, or take over
      that user's attempt.

## Technical Notes

- Treat `pagehide`/unload as best-effort; do not rely on it as the sole cleanup mechanism.
- Same-user reclamation must coordinate with the manager lock and worker-owned browser-gate release.
- Never wait for worker teardown while holding the manager lock.
- Do not leak which other user owns a busy attempt.

## Dependencies

### Requires

- Existing remote-auth manager cancellation and active-attempt ownership.
- 003-preserve-viewport-and-lifecycle-usability

### Enables

- Reliable repeated real-device acceptance testing and production self-recovery.

## Edge Cases

| Scenario | Expected Behavior |
|----------|-------------------|
| WebView process is killed with no unload | A follow-up same-user `/connect` replaces the attempt immediately |
| User briefly switches apps and sends `/connect` | The newer same-user request is authoritative |
| Worker teardown exceeds retry window | User gets a precise short retry message; no second browser starts |
| Different user is active | Existing privacy-safe busy response remains |
| Old viewer polls after cancellation | Terminal cancellation remains authoritative and liveness does not revive the attempt |
| Successful capture races reclamation | Existing manager lock produces either captured success or cancellation, never both |
| Two same-user `/connect` requests race | The latest request wins and at most one attempt owns the browser lease |

## Out of Scope

- Concurrent remote browsers or per-user VNC port allocation.
- Allowing one user to inspect or cancel another user's login.
