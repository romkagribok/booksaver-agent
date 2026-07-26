---
intent: 014-remote-auth-display-reliability
phase: inception
status: complete
created: 2026-07-26T17:55:43.000Z
updated: 2026-07-26T17:55:43.000Z
---

# Requirements: Remote Authentication Display Reliability

## Intent Overview

Correct the production `/connect` gray-screen defect without weakening the remote-authentication
trust boundary. The server-side mobile Chromium session already renders Booking.com correctly; the
Telegram Mini App must render those VNC framebuffer updates and explain viewer failures visibly.

## Business Goals

| Goal | Success Metric | Priority |
|------|----------------|----------|
| Restore `/connect` usability | Booking.com mobile sign-in pixels render in Telegram mobile and desktop clients | Must |
| Preserve least-privilege browser policy | Only the data-image capability required by noVNC is added | Must |
| Make future failures diagnosable | Viewer connection failures replace the indefinite gray screen with an actionable status | Must |

## Functional Requirements

### FR-1: Render noVNC framebuffer image updates
- **Description**: Permit noVNC to decode the inline image rectangles used by compressed VNC framebuffer updates while retaining the deny-by-default Content Security Policy.
- **Acceptance Criteria**:
  - The `/connect` CSP allows `data:` images and does not allow arbitrary remote image origins.
  - Existing script nonces, same-origin HTTPS/WebSocket restrictions, frame blocking, and form blocking remain intact.
  - A real remote-auth attempt can render the already-running `480×960` Android-emulated Chromium login page instead of a gray framebuffer.
- **Priority**: Must
- **Related Stories**: US-095

### FR-2: Explain noVNC connection failures
- **Description**: Report viewer security, credential, connection, and disconnection failures in the Mini App status area instead of leaving an unexplained gray screen.
- **Acceptance Criteria**:
  - RFB security failures display a safe, non-secret error.
  - Unexpected disconnects display a safe retry instruction.
  - User-requested cancellation and terminal server outcomes are not overwritten by a misleading viewer error.
  - Capability-bearing paths, WebSocket tokens, cookies, and Booking.com content remain absent from logs and messages.
- **Priority**: Must
- **Related Stories**: US-096

## Non-Functional Requirements

### Security

- Keep `default-src 'none'`, nonce-bound scripts/styles, same-origin requests, the exact WSS origin,
  `frame-ancestors 'none'`, and `form-action 'none'`.
- Add only `data:` to `img-src`; do not add `blob:`, `https:`, wildcards, or third-party origins.

### Reliability

- The change must work with the packaged noVNC version and its `Display.imageRect()` data-URL path.
- Viewer errors must not interfere with the existing 600-second expiry/cancellation cleanup.

### Verification

- Unit tests must pin the CSP and safe viewer event wiring.
- The relevant remote-auth suite and full repository quality gate must pass.
- Production acceptance requires a real Telegram `/connect` attempt on both mobile and desktop.

## Constraints

- This is a defect fix to the existing Intent 012 remote-auth gateway; it does not redesign session
  storage, Telegram identity verification, Caddy routing, or Booking.com authentication detection.
- The VPS browser remains Android-emulated mobile Chromium streamed through noVNC.
- Commit, push, and production deployment require a separate explicit approval after review.

## Assumptions and Decisions

- Live diagnosis captured a non-gray Booking.com mobile sign-in framebuffer directly from x11vnc.
- The deployed CSP is confirmed as `img-src 'none'`.
- Packaged noVNC creates `data:` image URLs for compressed image rectangles.
- The user's instruction to apply and document the diagnosed fix satisfies the inception scope and
  construction-start checkpoints; final Git and deployment actions remain held.

## Scope Exclusions

- Replacing noVNC, changing the mobile device profile, adding a window manager, or exposing raw VNC.
- Native Booking.com app automation, credential collection by BookSaver, or autonomous booking.
