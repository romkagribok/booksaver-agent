---
id: 003-preserve-viewport-and-lifecycle-usability
unit: 001-device-aware-remote-auth-viewer
intent: 016-device-aware-remote-auth-viewer
status: complete
priority: must
created: 2026-07-26T22:14:47.000Z
assigned_bolt: 030-device-aware-remote-auth-viewer
implemented: true
---

# Story: 003-preserve-viewport-and-lifecycle-usability

## User Story

**As a** Telegram user operating the streamed browser
**I want** the canvas, controls, and status to remain usable as the viewport and session change
**So that** I am never stranded behind the keyboard or an ambiguous connection state.

## Acceptance Criteria

- [x] **Given** Telegram viewport information is available, **When** the Mini App expands or the
      keyboard changes visible height, **Then** the canvas scales into the remaining space and the
      input dock stays visible.
- [x] **Given** the keyboard reduces available height, **When** the user last touched a remote form
      field, **Then** width remains readable and that region is panned into the upper visible area.
- [x] **Given** Telegram viewport information is unavailable, **When** the browser viewport changes,
      **Then** dynamic CSS viewport and safe-area fallbacks preserve reachable controls.
- [x] **Given** the native keyboard closes, **When** stable height returns, **Then** the canvas
      expands without reloading or reconnecting the remote browser.
- [x] **Given** the viewer is connected, **When** status becomes compact, **Then** help remains
      rediscoverable and direct Booking.com login guidance remains available.
- [x] **Given** success, cancellation, expiry, or failure, **When** the server state becomes terminal,
      **Then** the keyboard hides, input clears, and all remote-input controls are disabled.
- [x] **Given** RFB disconnects unexpectedly while the server attempt remains active, **When** the
      viewer retries, **Then** input is disabled and cleared while it makes only a bounded number of
      viewer reconnection attempts before showing safe return-and-retry guidance.
- [x] **Given** an unexpected RFB disconnect races with a server terminal outcome, **When** status is
      rendered, **Then** the authoritative terminal outcome is not overwritten by a viewer error.

## Technical Notes

- Preserve `rfb.scaleViewport=true` and avoid remote-session resizing or viewer reloads.
- Use Telegram viewport/safe-area signals as progressive enhancement, not a dependency.
- Keep vertical swipe/fullscreen behavior unchanged.

## Dependencies

### Requires

- 001-present-device-adaptive-viewer
- 002-type-with-native-mobile-keyboard

### Enables

- 004-preserve-credential-and-desktop-safety

## Edge Cases

| Scenario | Expected Behavior |
|----------|-------------------|
| Device rotates while keyboard is open | Dock remains reachable and canvas rescales |
| iOS safe-area inset | Controls do not sit behind the home indicator |
| Terminal state during typing | Buffer clears and no further key is sent |
| Clean user cancellation | Existing cancellation outcome is shown, not a disconnect error |

## Out of Scope

- Forcing Telegram fullscreen or changing its swipe-to-close policy.
- Resizing the Xvfb display or remote Chromium window per client.
