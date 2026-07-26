---
id: 001-present-device-adaptive-viewer
unit: 001-device-aware-remote-auth-viewer
intent: 016-device-aware-remote-auth-viewer
status: complete
priority: must
created: 2026-07-26T22:14:47.000Z
assigned_bolt: 030-device-aware-remote-auth-viewer
implemented: true
---

# Story: 001-present-device-adaptive-viewer

## User Story

**As a** Telegram user opening `/connect` on any supported device
**I want** the streamed browser controls to match my available input capabilities
**So that** I immediately understand how to operate the remote Booking.com login.

## Acceptance Criteria

- [x] **Given** Telegram provides a platform value, **When** the viewer initializes, **Then** it uses
      the value only as a presentation hint.
- [x] **Given** Telegram platform data is missing or inaccurate, **When** touch or coarse-pointer
      capability exists, **Then** the touch-first controls remain available.
- [x] **Given** the RFB session is not connected, **When** the viewer is authorizing or connecting,
      **Then** remote-input controls are visibly disabled.
- [x] **Given** a touch-first viewer connects, **When** the user sees the canvas, **Then** concise
      guidance explains to tap a Booking.com field and then tap `Keyboard`.
- [ ] **Given** the remote Chromium starts on the VPS, **When** its framebuffer becomes visible,
      **Then** Booking.com occupies an app-like surface without desktop tabs or an address bar.
      **Operations gate**: Linux/Xvfb smoke remains pending.
- [x] **Given** a desktop viewer connects, **When** the user types with a physical keyboard,
      **Then** current noVNC input continues to work and mobile controls remain unobtrusive.
- [x] **Given** the viewer presents an action control, **Then** it has an accessible name, visible
      state, and at least a 44-by-44 CSS-pixel target.

## Technical Notes

- Combine `Telegram.WebApp.platform` with touch/pointer capability detection.
- Keep all discovery local; do not add it to the signed exchange or session API.
- Preserve the configured Android Playwright context for every viewer client.
- Smoke-test kiosk/app-like launch under the actual Linux/Xvfb container before accepting it.

## Dependencies

### Requires

- Existing remote-auth gateway and RFB connection.

### Enables

- 002-type-with-native-mobile-keyboard
- 003-preserve-viewport-and-lifecycle-usability

## Edge Cases

| Scenario | Expected Behavior |
|----------|-------------------|
| Unknown Telegram platform | Capability detection supplies a safe viewer mode |
| Touch-enabled laptop | Touch controls remain available without disabling physical input |
| RFB connection delay | Controls remain disabled and connecting status stays visible |
| Kiosk/app flag behaves differently in container Chromium | Fail the smoke gate rather than ship an extra page or unusable window |

## Out of Scope

- Selecting a server-side browser profile from the client platform.
- Reproducing native Android or iOS browser chrome.
