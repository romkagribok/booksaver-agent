---
stage: implement
bolt: 030-device-aware-remote-auth-viewer
created: 2026-07-26T22:56:00Z
---

## Implementation Walkthrough: Device-Aware Remote Authentication Viewer

### Summary

The remote-auth Mini App now adapts to touch and desktop clients, opens a focusable native-keyboard
bridge on phones, forwards mobile IME input through noVNC, and keeps the remote page and control dock
usable as the viewport changes. The VPS browser launches in kiosk presentation while retaining the
fixed Android-emulated Playwright context.

### Completed Work

- [x] `src/booksaver/infrastructure/remote_auth/viewer.py` - Extracts the credential-blind viewer,
  adds platform/touch discovery, password-semantic capture input, noVNC input-diff bridge, touch
  controls, safe-area/viewport handling, one bounded RFB reconnect, and lifecycle cleanup.
- [x] `src/booksaver/infrastructure/remote_auth/gateway.py` - Delegates viewer rendering while
  preserving nonce CSP, same-origin APIs, secure cookie, and no-store behavior.
- [x] `src/booksaver/infrastructure/remote_auth/browser_runner.py` - Adds kiosk launch arguments and
  fail-closed validation for the RFB, Keyboard, keysym, and keysym-definition modules.
- [x] `tests/unit/test_remote_auth_gateway.py` - Covers the touch controls, credential boundary,
  module imports, viewport signals, CSP, safe errors, and close hook.
- [x] `tests/unit/test_remote_browser_runner.py` - Covers kiosk arguments and required module files.
- [x] `tests/integration/test_remote_auth_viewer_browser.py` - Runs the viewer in Playwright with
  fake Telegram and noVNC endpoints and proves focus, character/backspace/Tab/Enter forwarding,
  persistent keyboard focus, and pagehide cancellation.

### Key Decisions

- **Reuse noVNC input semantics**: The viewer follows noVNC 1.6's sentinel-buffer diff behavior
  instead of defining another input transport.
- **Keep credentials off BookSaver HTTP**: The capture input exists only inside the WebView and
  translates transient input directly into RFB key events.
- **Preserve readable width**: Keyboard mode gives the RFB target a width-derived tall surface in a
  scrollable viewport rather than scaling the remote browser to the reduced keyboard height.
- **Presentation-only detection**: Telegram platform and browser touch signals never affect
  authorization, browser ownership, or the configured Android context.
- **Kiosk, not app URL**: `--kiosk` removes misleading browser chrome without introducing an
  independently navigated `--app` page.

### Deviations from Plan

Local Docker is unavailable, so Linux/Xvfb kiosk rendering could not be proven before the
pre-deployment review. The code validates its launch contract and noVNC module layout; live VPS and
real Telegram Android/iOS/Desktop checks remain explicit release gates.

### Dependencies Added

None.
