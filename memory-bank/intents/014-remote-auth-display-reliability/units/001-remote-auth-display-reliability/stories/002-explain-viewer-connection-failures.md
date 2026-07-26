---
id: 002-explain-viewer-connection-failures
unit: 001-remote-auth-display-reliability
intent: 014-remote-auth-display-reliability
status: complete
priority: must
created: 2026-07-26T17:55:43.000Z
assigned_bolt: 027-remote-auth-display-reliability
implemented: true
---

# Story: Explain Remote Viewer Connection Failures

## User Story

**As a** Telegram BookSaver user
**I want** a clear message when the remote viewer cannot connect
**So that** I know to retry `/connect` instead of waiting on an unexplained gray screen

## Acceptance Criteria

- [ ] **Given** noVNC reports a security failure, **When** the event fires, **Then** the status area
  shows a safe connection-failed message.
- [ ] **Given** noVNC disconnects unexpectedly, **When** the event reports an unclean disconnect,
  **Then** the status area tells the user to close the page and retry `/connect`.
- [ ] **Given** the session has already succeeded, failed, expired, or been cancelled, **When** the
  viewer disconnects, **Then** the terminal server status remains authoritative.
- [ ] **Given** any viewer failure, **When** feedback is rendered or logged, **Then** it contains no
  WebSocket token, launch token, cookie, capability path, or Booking.com content.

## Technical Notes

- Attach noVNC `securityfailure` and `disconnect` event listeners before relying on the viewer.
- Track terminal server state separately from the RFB object.

## Dependencies

### Requires

- US-095 framebuffer policy correction.

### Enables

- Production acceptance testing and faster future diagnosis.

## Edge Cases

| Scenario | Expected Behavior |
|----------|-------------------|
| Clean disconnect after success/cancel | Do not replace the terminal status |
| Temporary polling error | Existing safe polling message remains |
| Event object contains server details | Do not interpolate untrusted details |

## Out of Scope

- Automatic retries that could create multiple browser attempts.
