---
unit: 001-device-aware-remote-auth-viewer
intent: 016-device-aware-remote-auth-viewer
phase: inception
status: complete
unit_type: cli
default_bolt_type: simple-construction-bolt
created: 2026-07-26T22:14:47.000Z
updated: 2026-07-26T22:45:44.000Z
---

# Unit Brief: Device-Aware Remote Authentication Viewer

## Purpose

Make the existing Telegram-hosted noVNC viewer usable and polished on touch-only devices without
changing the server-side mobile browser, authentication, or session-capture model.

## Scope

### In Scope

- Local client platform/touch discovery for presentation.
- Touch-first viewer controls and concise first-use guidance.
- noVNC-compatible password-semantic capture-input keyboard bridge.
- App-like/kiosk remote Chromium presentation without desktop tabs/address chrome.
- Text, Unicode, backspace, Tab, and Return forwarding.
- Dynamic viewport/safe-area layout and keyboard lifecycle cleanup.
- Best-effort unload cancellation and immediate same-user abandoned-attempt recovery.
- Desktop, security, accessibility, and terminal-state regressions.
- Browser-level test harness using the existing Playwright dependency.

### Out of Scope

- Android emulation, native app automation, or changing the Playwright device profile.
- Credential endpoints, password management, clipboard synchronization, or persistent viewer state.
- Changes to Telegram identity verification, single-browser exclusivity, Booking.com navigation
  policy, authenticated cookie capture, or monitoring checks.
- Federated identity-provider login.

## Assigned Requirements

| FR | Requirement | Priority |
|----|-------------|----------|
| FR-1 | Discover viewer input capabilities | Must |
| FR-2 | Open the device's native software keyboard | Must |
| FR-3 | Relay mobile text input through noVNC | Must |
| FR-4 | Provide a touch-first input dock and guidance | Must |
| FR-5 | Adapt the viewer to dynamic viewport and safe areas | Must |
| FR-6 | Preserve clear lifecycle and recovery states | Must |
| FR-7 | Release abandoned viewers and permit safe same-user retry | Must |

## Viewer Concepts

| Concept | Description |
|---------|-------------|
| Viewer capabilities | Untrusted platform, touch, coarse-pointer, viewport, and safe-area presentation hints |
| Input mode | Explicit open/closed local native-keyboard state |
| Input dock | Keyboard, Next, Enter, help, and Cancel controls around the remote canvas |
| Keyboard buffer | Transient password-semantic input state used to translate mobile input into RFB keys |
| Viewer lifecycle | Authorizing, connecting, connected, input-active, terminal, and disconnected states |
| Attempt ownership | Telegram user that may replace its own current nonterminal attempt |

## Key Operations

| Operation | Description | Inputs | Outputs |
|-----------|-------------|--------|---------|
| Detect capabilities | Choose touch-first or desktop presentation | Telegram platform and browser features | Viewer presentation mode |
| Toggle keyboard | Focus or blur the local hidden input | Direct control tap | Native keyboard open/closed |
| Forward input | Translate local input changes and key events | Characters and editing events | RFB `sendKey` events |
| Send shortcut | Advance or submit a remote form | Next or Enter tap | Tab or Return RFB event |
| Reflow viewer | Preserve visible canvas and controls | Telegram/CSS viewport changes | Scaled stable layout |
| Terminate input | Clear sensitive transient state | Success, cancel, expiry, failure, disconnect | Disabled controls and cleared buffer |
| Reclaim attempt | Replace an abandoned attempt for its owning Telegram user | Same-user `/connect` | Fresh login link or short teardown guidance |

## Story Summary

| Metric | Count |
|--------|-------|
| Total Stories | 5 |
| Must Have | 5 |
| Should Have | 0 |
| Could Have | 0 |

### Stories

| Story ID | Title | Priority | Status |
|----------|-------|----------|--------|
| 001-present-device-adaptive-viewer | Present a device-adaptive streamed viewer | Must | Complete |
| 002-type-with-native-mobile-keyboard | Type with the native mobile keyboard | Must | Complete |
| 003-preserve-viewport-and-lifecycle-usability | Preserve viewport and lifecycle usability | Must | Complete |
| 004-preserve-credential-and-desktop-safety | Preserve credential and desktop safety | Must | Complete |
| 005-recover-from-abandoned-viewer | Recover from an abandoned viewer | Must | Complete |

## Dependencies

### Depends On

| Unit | Reason |
|------|--------|
| Intent 012 remote-authentication gateway | Provides signed viewer, session state, RFB transport, and lifecycle |
| Intent 014 display reliability | Provides framebuffer-compatible CSP and safe viewer error handling |
| Intent 015 direct Booking authentication | Provides the current Booking.com-only navigation and guidance boundary |

### Depended By

No planned unit depends on this usability correction.

### External Dependencies

| System | Purpose | Risk |
|--------|---------|------|
| Telegram Android/iOS/Desktop | Mini App host, platform hints, and real-device keyboard behavior | High compatibility risk |
| noVNC 1.6 | RFB, keyboard, keysym, and mobile input behavior | Medium packaged-version risk |
| Booking.com | Direct sign-in UI rendered as remote pixels | Medium third-party-layout risk |

## Technical Context

### Suggested Technology

Keep the stdlib Python gateway and its generated same-origin HTML/ES modules. Import the packaged
noVNC keyboard and keysym modules next to the existing RFB module. Use a visually hidden
password-semantic capture input, an explicit input dock, Telegram/browser feature detection, CSS
dynamic viewport/safe-area fallbacks, an Xvfb-verified app-like Chromium launch, authenticated
viewer liveness, and the existing Playwright dependency for browser-level verification. Start with
a container compatibility spike for the capture input, noVNC modules, and Chromium kiosk behavior.

### Integration Points

| Integration | Type | Protocol |
|-------------|------|----------|
| Telegram Mini App | Client presentation and signed authorization | HTTPS JavaScript bridge |
| Remote-auth gateway | Viewer document and session polling | Same-origin HTTPS |
| noVNC/websockify | Framebuffer and input transport | Token-gated WSS/RFB |
| Xvfb Chromium | Remote Booking.com interaction | VNC keyboard/pointer events |

### Data Storage

No new persistent data. Client capabilities and keyboard buffer exist only for the viewer lifetime.

## Constraints

- Client platform values cannot affect authentication or the server-side browser profile.
- The keyboard must open from a direct local user gesture.
- Typed credential text cannot be logged, persisted, posted, echoed, or clipboard-synced.
- The current deny-by-default CSP and one-time viewer capability remain intact.
- No new runtime dependency or JavaScript toolchain.

## Success Criteria

### Functional

- [ ] Android and iOS users can complete direct Booking.com login without physical keyboards.
      **Operations gate**: native Telegram acceptance pending.
- [x] Keyboard, Next, Enter, Hide, and Cancel remain understandable and reachable.
- [x] Remote input remains correct across repeat open/hide cycles.
- [x] Viewer controls and canvas remain usable as the native keyboard changes viewport height.
- [ ] The streamed surface shows Booking.com without misleading desktop tabs or an address bar.
      **Operations gate**: Linux/Xvfb kiosk smoke pending.
- [x] A follow-up same-user `/connect` safely reclaims an abandoned attempt without weakening the
      global single-browser lease.

### Non-Functional

- [x] Platform/touch discovery is presentation-only and has safe fallbacks.
- [x] No credential text reaches HTTP, Telegram, logs, clipboard, or persistence.
- [x] Desktop keyboard/mouse behavior and all current remote-auth lifecycle behavior remain intact.
- [ ] Real-device acceptance covers Telegram Android, iOS, and Desktop.

### Quality

- [x] Gateway unit tests and Playwright browser-level viewer tests cover the critical input states.
- [x] Ruff, mypy, targeted tests, full tests, and AI-DLC validators pass.
- [ ] Code and construction artifacts receive human review before Git or deployment.

## Bolt Suggestions

| Bolt | Type | Stories | Objective |
|------|------|---------|-----------|
| 030-device-aware-remote-auth-viewer | Simple Construction | 001-004 | Deliver and verify the adaptive viewer and keyboard experience |
| 031-remote-auth-attempt-recovery | Simple Construction | 005 | Add race-safe abandoned-attempt recovery after the viewer shell is stable |

## Notes

The primary residual risk is mobile WebView behavior that cannot be proven by desktop automation.
Construction must treat Android/iOS Telegram acceptance as a release gate rather than relying only
on generated-HTML assertions.
