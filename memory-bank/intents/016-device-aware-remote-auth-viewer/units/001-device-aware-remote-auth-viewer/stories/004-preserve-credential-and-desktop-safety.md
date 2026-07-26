---
id: 004-preserve-credential-and-desktop-safety
unit: 001-device-aware-remote-auth-viewer
intent: 016-device-aware-remote-auth-viewer
status: complete
priority: must
created: 2026-07-26T22:14:47.000Z
assigned_bolt: 030-device-aware-remote-auth-viewer
implemented: true
---

# Story: 004-preserve-credential-and-desktop-safety

## User Story

**As a** BookSaver user and self-hosting owner
**I want** mobile input convenience without a new credential or browser-security pathway
**So that** phone usability does not weaken the existing authentication boundary.

## Acceptance Criteria

- [x] **Given** a user types credentials, **When** input is forwarded, **Then** plaintext exists only
      transiently in the password-semantic capture input/device IME and RFB event path and never
      enters an HTTP request, Telegram message, log, clipboard, analytics event, or persistent store.
- [x] **Given** the viewer page is served, **When** its security headers are inspected, **Then** the
      current deny-by-default CSP, exact HTTPS/WSS origin restrictions, frame denial, form denial,
      no-store policy, and referrer protection remain intact.
- [x] **Given** a desktop user connects, **When** they use physical keyboard and mouse input, **Then**
      behavior remains compatible with the current noVNC viewer.
- [x] **Given** a touch or unknown client connects, **When** platform discovery fails, **Then** an
      accessible keyboard fallback remains available.
- [x] **Given** automated verification runs, **When** the fixture viewer receives touch and input
      events, **Then** focus, key translation, buffer clearing, and terminal cleanup are observed
      without a live credential.
- [x] **Given** construction is otherwise complete, **When** release readiness is assessed, **Then**
      real Telegram Android, iOS, and Desktop acceptance remains an explicit deployment gate.

## Technical Notes

- Prefer a Playwright browser-level fixture around the generated viewer and a fake RFB module over
  substring-only assertions for interactive behavior.
- Add a container/build compatibility gate for the noVNC input modules imported by the viewer.
- Preserve safe viewer messages and the Booking.com-only document-navigation policy.
- Do not claim protection from compromised VPS root.

## Dependencies

### Requires

- 002-type-with-native-mobile-keyboard
- 003-preserve-viewport-and-lifecycle-usability

### Enables

- Production acceptance of the device-aware viewer.

## Edge Cases

| Scenario | Expected Behavior |
|----------|-------------------|
| Test failure prints DOM | Hidden input values are not included in assertion/error messages |
| Unknown touch browser | Fallback control is reachable without trusting platform identity |
| RFB disconnect while key is held | Input is disabled and listener state is released |
| Existing physical keyboard | No duplicate key forwarding occurs |

## Out of Scope

- Protecting the remote session from a compromised self-hosted VPS.
- Building a password vault, credential proxy, or device-local authentication handoff.
