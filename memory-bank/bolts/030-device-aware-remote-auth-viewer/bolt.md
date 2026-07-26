---
id: 030-device-aware-remote-auth-viewer
unit: 001-device-aware-remote-auth-viewer
intent: 016-device-aware-remote-auth-viewer
type: simple-construction-bolt
status: complete
stories:
  - 001-present-device-adaptive-viewer
  - 002-type-with-native-mobile-keyboard
  - 003-preserve-viewport-and-lifecycle-usability
  - 004-preserve-credential-and-desktop-safety
created: 2026-07-26T22:14:47.000Z
started: 2026-07-26T22:45:44.000Z
completed: "2026-07-26T23:00:38Z"
current_stage: null
stages_completed:
  - name: plan
    completed: 2026-07-26T22:45:44.000Z
    artifact: implementation-plan.md
  - name: implement
    completed: 2026-07-26T22:56:00.000Z
    artifact: implementation-walkthrough.md
  - name: test
    completed: 2026-07-26T23:00:02.000Z
    artifact: test-walkthrough.md
requires_bolts:
  - 026-remote-authentication-gateway
  - 027-remote-auth-display-reliability
  - 029-direct-booking-auth-only
enables_bolts:
  - 031-remote-auth-attempt-recovery
requires_units: []
blocks: false
complexity:
  avg_complexity: 2
  avg_uncertainty: 2
  max_dependencies: 2
  testing_scope: 3
---

# Bolt: 030-device-aware-remote-auth-viewer

## Overview

Deliver the complete adaptive Mini App viewer experience as one cohesive UI/integration change.

## Objective

Let Android and iOS Telegram users complete direct Booking.com login using their native software
keyboard while preserving the fixed Android remote-browser profile, desktop behavior, credential
boundaries, and remote-auth lifecycle.

## Stories Included

- **001-present-device-adaptive-viewer**: Present a device-adaptive streamed viewer (Must)
- **002-type-with-native-mobile-keyboard**: Type with the native mobile keyboard (Must)
- **003-preserve-viewport-and-lifecycle-usability**: Preserve viewport and lifecycle usability (Must)
- **004-preserve-credential-and-desktop-safety**: Preserve credential and desktop safety (Must)

## Bolt Type

**Type**: Simple Construction Bolt
**Definition**: `.specsmd/aidlc/templates/construction/bolt-types/simple-construction-bolt.md`

## Stages

- [x] **1. Plan**: Complete → `implementation-plan.md`
- [x] **2. Implement**: Complete → source, tests, and `implementation-walkthrough.md`
- [x] **3. Test**: Complete → `test-walkthrough.md`

## Planned Technical Approach

1. Run a container compatibility spike for a password-semantic noVNC input, the packaged noVNC
   modules, and controlled Chromium kiosk behavior.
2. Launch the remote Chromium in an Xvfb-verified app-like/kiosk presentation while preserving the
   fixed Android Playwright context and one controlled Booking.com page.
3. Refine the viewer layout into a compact status region, readable clipped/scalable canvas, and
   safe-area-aware input dock.
4. Detect Telegram platform plus actual touch/pointer capabilities locally and select a
   touch-primary or desktop-primary presentation.
5. Add a password-semantic capture input and adapt the installed noVNC 1.6 `Keyboard`, key table,
   keysym, and input-diff behavior.
6. Add Keyboard/Hide, Next, Enter, help, and Cancel interactions with disabled and terminal states.
7. Reflow against Telegram viewport changes and CSS dynamic-viewport/safe-area fallbacks, preserving
   readable width and panning the last remote touch region above the keyboard.
8. Extract enough viewer behavior to support a Playwright fixture with a fake RFB module, while
   retaining gateway/CSP unit coverage and no new runtime dependency.
9. Run real-device Telegram acceptance on Android, iOS, and Desktop before deployment.

## Dependencies

### Requires

- **026-remote-authentication-gateway**: signed Mini App, RFB session, and lifecycle (Complete)
- **027-remote-auth-display-reliability**: framebuffer CSP and safe viewer errors (Complete)
- **029-direct-booking-auth-only**: Booking.com navigation and guidance boundary (Complete)

### Enables

- Bolt 031 remote-auth attempt recovery.
- Practical self-service Booking.com session connection from touch-only devices.

## Success Criteria

- [x] All four included stories are implemented; environment-specific acceptance remains an
      Operations gate below.
- [ ] A phone user can open, type, advance, submit, and hide the native keyboard without physical
      hardware. **Operations gate**: real Android/iOS Telegram acceptance pending.
- [x] Canvas and controls remain usable across keyboard, viewport, orientation, and terminal changes.
- [ ] The streamed surface is app-like and its lifecycle exposes the hook needed by Bolt 031.
      **Operations gate**: Linux/Xvfb kiosk smoke pending.
- [x] Platform discovery cannot affect authentication, session ownership, or mobile-price context.
- [x] No credential text gains an HTTP, Telegram, persistence, clipboard, or logging path.
- [x] Desktop physical input and current remote-auth security/lifecycle tests remain green.
- [x] Browser-level fixture verification is complete.
- [ ] Real Telegram Android/iOS/Desktop acceptance is complete.
- [ ] Final product-owner merge review is complete.

## Execution Authorization

The product owner approved the complete design and authorized uninterrupted construction through
the final pre-merge review. Git, merge, push, and deployment remain held for final approval.
