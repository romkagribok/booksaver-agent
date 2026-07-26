---
stage: plan
bolt: 030-device-aware-remote-auth-viewer
created: 2026-07-26T22:45:44Z
---

## Implementation Plan: Device-Aware Remote Authentication Viewer

### Objective

Make the Telegram Mini App's streamed Booking.com browser practical on touch-only Android and iOS
devices without changing the fixed server-side Android browser profile or introducing a credential
transport through BookSaver.

### Deliverables

- Capability-aware touch and desktop viewer presentation.
- A password-semantic local capture input using the packaged noVNC keyboard and keysym behavior.
- Keyboard, Hide keyboard, Next, Enter, Help, and Cancel controls with safe lifecycle states.
- Dynamic viewport and safe-area layout that keeps controls reachable during software-keyboard use.
- App-like Chromium kiosk launch with required noVNC module validation.
- Browser/gateway tests for capability fallback, input lifecycle, terminal cleanup, page-close
  cancellation, CSP, desktop regression, and browser launch arguments.

### Technical Approach

Keep the viewer as same-origin generated HTML with no build tool. Import the packaged noVNC RFB,
Keyboard, keysym table, and keysym-definition modules. Adapt noVNC's established sentinel-buffer
input-diff behavior around a visually hidden `type=password` input, forwarding only RFB key events.

Discover Telegram platform and touch/coarse-pointer capabilities locally. Treat these only as
presentation hints. Use a safe-area-aware flex layout, Telegram viewport notifications,
`visualViewport`, and dynamic viewport fallbacks. When input mode is active, prefer a clipped
viewport that preserves readable remote width and keeps the last touched remote region visible.

Launch headed Chromium with kiosk presentation inside the existing 480-by-960 Xvfb display while
retaining the fixed Pixel-class Playwright context, Booking.com-only navigation policy, one page,
and worker-owned cleanup.

Add `pagehide` best-effort authenticated cancellation after viewer exchange, excluding bfcache
transitions and never using `visibilitychange` as a cancellation signal. Bolt 031 remains the
correctness fallback when that event is not delivered.

### Verification

- Focused gateway, manager, and browser-runner unit tests.
- Browser-level Playwright fixture when supported locally; otherwise deterministic HTML/module
  contract coverage plus a recorded real-device acceptance gate.
- Ruff, mypy, full pytest suite, AI-DLC validators, and diff hygiene.
- Deployed Android, iOS, and Telegram Desktop acceptance remains required before production release.

### Risks and Controls

- Packaged noVNC API drift: validate all imported module files before launch and fail closed.
- Mobile IME differences: reuse noVNC's input-diff semantics and require real-device acceptance.
- Kiosk/Xvfb differences: unit-test launch contract and retain a VPS smoke gate because local Docker
  is unavailable.
- Credential exposure: no input HTTP endpoint, clipboard, logging, storage, analytics, or visible
  echo.
