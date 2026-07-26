---
id: 001-render-remote-browser-framebuffer
unit: 001-remote-auth-display-reliability
intent: 014-remote-auth-display-reliability
status: complete
priority: must
created: 2026-07-26T17:55:43.000Z
assigned_bolt: 027-remote-auth-display-reliability
implemented: true
---

# Story: Render the Remote Mobile-Browser Framebuffer

## User Story

**As a** Telegram BookSaver user
**I want** the `/connect` viewer to paint the remote Booking.com login page
**So that** I can authenticate my own account instead of seeing a gray screen

## Acceptance Criteria

- [ ] **Given** noVNC receives compressed image rectangles, **When** it creates inline data images,
  **Then** the Mini App CSP permits those images to render.
- [ ] **Given** the CSP is inspected, **When** allowed image sources are evaluated, **Then** only
  `data:` is allowed and arbitrary same-origin/remote image loading remains blocked.
- [ ] **Given** the deployed mobile profile, **When** `/connect` starts, **Then** the same `480×960`
  Android-emulated Chromium display remains the source on mobile and desktop Telegram clients.

## Technical Notes

- Change only `img-src 'none'` to `img-src data:`.
- noVNC `core/display.js` uses `new Image()` with a `data:` URL for image rectangles.

## Dependencies

### Requires

- Completed remote-auth gateway and its existing CSP.

### Enables

- US-096 viewer failure feedback.

## Edge Cases

| Scenario | Expected Behavior |
|----------|-------------------|
| Remote image URL is injected | CSP blocks it |
| Inline script lacks the per-response nonce | CSP blocks it |
| Viewer runs in desktop Telegram | The server-side context remains Android mobile |

## Out of Scope

- Changing VNC encodings or exposing raw VNC ports.
