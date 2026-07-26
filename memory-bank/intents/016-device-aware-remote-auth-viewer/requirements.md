---
intent: 016-device-aware-remote-auth-viewer
phase: inception
status: complete
created: 2026-07-26T22:14:47.000Z
updated: 2026-07-26T22:45:44.000Z
---

# Requirements: Device-Aware Remote Authentication Viewer

## Intent Overview

Make the streamed Booking.com login practical and reassuring on phones, tablets, and desktops.
BookSaver must continue to run one Android-emulated Chromium session on the trusted VPS for mobile
web behavior, while the Telegram Mini App viewer adapts its controls to the user's actual input
capabilities and provides a native software-keyboard bridge for touch-only devices.

## Business Goals

| Goal | Success Metric | Priority |
|------|----------------|----------|
| Make phone-only login usable | A user can complete direct Booking.com email/password login in Telegram on Android and iOS without a physical keyboard | Must |
| Preserve mobile-web pricing context | Viewer adaptation never changes the configured Android Playwright profile used by login or checks | Must |
| Make the streamed browser feel intentional | Users can understand how to focus, type, advance, submit, hide the keyboard, cancel, and recover from viewer failures | Must |
| Remove misleading desktop chrome | The remote display presents Booking.com in a verified app-like surface without tabs or an address bar | Must |
| Recover from an abandoned viewer | A follow-up `/connect` from the same user can reclaim their abandoned login without waiting for the full timeout | Must |
| Preserve existing trust boundaries | Typed credentials never enter Telegram messages, BookSaver HTTP requests, persistence, clipboard handling, or logs | Must |

## Functional Requirements

### FR-1: Discover viewer input capabilities
- **Description**: The Mini App must adapt its presentation using Telegram's client platform and
  browser capability signals without treating either as identity or authorization evidence.
- **Acceptance Criteria**:
  - The viewer reads `Telegram.WebApp.platform` when available.
  - Touch capability is independently detected using pointer/touch feature detection so an unknown,
    missing, or inaccurate Telegram platform value does not make the viewer unusable.
  - Platform and capability values remain client-side presentation hints and are not persisted,
    logged, or used to select the server-side Playwright profile.
  - Android, iOS, desktop, web, and unknown-platform behavior has a defined safe fallback.
- **Priority**: Must
- **Related Stories**: US-101

### FR-2: Open the device's native software keyboard
- **Description**: A touch user must be able to deliberately open and close the native device
  keyboard while controlling the remote noVNC session.
- **Acceptance Criteria**:
  - A clearly labeled `Keyboard` control is available after the RFB connection is ready.
  - Activating the control during a direct user gesture focuses a local, visually hidden,
    password-semantic input and opens the Android or iOS software keyboard.
  - Activating `Hide keyboard`, reaching a terminal session state, or losing the RFB connection
    blurs and clears the local input.
  - The keyboard control is disabled while authorization or RFB connection is still pending.
  - Desktop physical-keyboard input continues to work without requiring the software-keyboard mode.
- **Priority**: Must
- **Related Stories**: US-102

### FR-3: Relay mobile text input through noVNC
- **Description**: The local input must translate mobile keyboard behavior into the active RFB
  session using the installed noVNC input model, including Android keyboards that do not emit
  complete hardware-style key events.
- **Acceptance Criteria**:
  - Ordinary characters, Unicode characters supported by noVNC, backspace, Return, and Tab reach
    the focused field in the remote Chromium session.
  - The bridge reuses noVNC's keyboard, keysym, and input-diff behavior rather than inventing a
    second remote-input protocol.
  - The local input buffer is cleared after committed input and BookSaver never visually echoes the
    entered credential text; the device IME may transiently process the current composition.
  - No per-keystroke HTTP request, Telegram message, clipboard write, or persistent storage occurs.
  - Input listeners and buffered text are released on terminal state or disconnect.
- **Priority**: Must
- **Related Stories**: US-102, US-104

### FR-4: Provide a touch-first input dock and guidance
- **Description**: Touch clients must receive a compact, predictable control surface that explains
  the unavoidable remote-canvas interaction without obscuring the Booking.com page.
- **Acceptance Criteria**:
  - Before first keyboard activation, concise guidance says: tap a Booking.com field, then tap
    `Keyboard`.
  - The connected touch layout exposes `Keyboard`, `Next`, `Enter`, and `Cancel` without requiring a
    physical keyboard or hidden gesture.
  - The remote Chromium launch uses a tested app-like or kiosk presentation so Booking.com content,
    rather than desktop tabs and an address bar, occupies the streamed surface.
  - `Next` sends Tab and `Enter` sends Return only through the active RFB session.
  - The keyboard button visibly communicates open/closed state and has an accessible label.
  - Guidance becomes compact after the user activates input mode but can be rediscovered without
    reloading the session.
  - Desktop clients retain an unobtrusive optional input fallback while prioritizing the streamed
    browser and physical keyboard.
- **Priority**: Must
- **Related Stories**: US-101, US-102

### FR-5: Adapt the viewer to dynamic mobile viewport and safe areas
- **Description**: The streamed browser and controls must remain visible when Telegram chrome,
  device safe areas, orientation, or the native software keyboard changes the usable viewport.
- **Acceptance Criteria**:
  - Layout uses Telegram viewport information when available and CSS dynamic-viewport/safe-area
    fallbacks otherwise.
  - Opening the software keyboard keeps the input dock visible and preserves readable canvas width
    instead of shrinking the remote field into an unusably small surface.
  - The viewer remembers the user's last remote touch position and, while the keyboard is open,
    keeps that region in the upper visible portion of a vertically clipped or scrollable canvas.
  - Closing the keyboard restores the canvas without reconnecting or restarting the remote browser.
  - Vertical Telegram swipe behavior and full-screen mode are not changed as part of this intent.
  - Buttons meet a minimum 44-by-44 CSS-pixel touch target and remain usable in portrait and
    landscape layouts.
- **Priority**: Must
- **Related Stories**: US-103

### FR-6: Preserve clear lifecycle and recovery states
- **Description**: The viewer must keep authorization, connecting, connected, keyboard-active,
  succeeded, cancelled, expired, failed, and unexpectedly disconnected states understandable.
- **Acceptance Criteria**:
  - Connecting states show progress while preventing premature input.
  - A compact connected state confirms that the remote browser is ready and direct Booking.com
    credentials are the supported path.
  - Terminal server outcomes take precedence over viewer errors and disable all remote-input
    controls.
  - Unexpected disconnects hide the keyboard, clear the buffer, and provide the existing safe
    instruction after a bounded viewer-only reconnect attempt while server state remains active.
  - Cancel remains explicit and distinct from typing controls and preserves existing cleanup.
- **Priority**: Must
- **Related Stories**: US-103, US-104

### FR-7: Reclaim abandoned viewers during safe same-user retry
- **Description**: A user who closes the Telegram viewer without pressing Cancel must be able to use
  a follow-up `/connect` to reclaim their own abandoned attempt instead of waiting for the full
  authentication timeout.
- **Acceptance Criteria**:
  - Explicit Cancel continues to end the viewer attempt and trigger normal browser cleanup.
  - A conservative viewer unload signal may perform best-effort authenticated cancellation, but
    correctness does not depend on WebView unload delivery or distinguishing close from suspension.
  - Temporary Telegram backgrounding or a `visibilitychange` alone never cancels the attempt.
  - A new `/connect` from the same Telegram user marks that user's current nonterminal attempt
    cancelled under the manager lock without accessing or reusing its viewer capability.
  - The reclaiming `/connect` waits only for a short, bounded worker teardown outside the manager
    lock and starts the replacement in the same command as soon as the old worker releases the
    browser lease.
  - If bounded teardown does not finish, no replacement browser starts and the same user receives a
    specific short retry instruction.
  - A retry never takes over another user's attempt and never permits two remote browsers to run
    concurrently.
  - If teardown is still in progress, the same user receives a specific short retry instruction
    rather than the misleading generic “another login is active” message.
- **Priority**: Must
- **Related Stories**: US-105

## Non-Functional Requirements

### Security

- Preserve the signed Telegram `initData` exchange, one-time viewer capabilities, HttpOnly session
  cookie, same-origin WSS route, Booking.com-only document navigation, and deny-by-default CSP.
- Do not broaden CSP sources or introduce third-party viewer code, analytics, telemetry, or a
  credential endpoint.
- Typed input may exist only transiently in the local password-semantic capture input, the device
  IME's current composition, and RFB key events over the authenticated WSS connection; BookSaver
  must never log, persist, visually echo, post, or clipboard-sync it.
- Client platform discovery is untrusted presentation data and must not affect authorization,
  session ownership, browser leasing, or mobile-price provenance.
- Documentation must continue to state that compromised VPS root can observe the remote session;
  this intent does not claim device-local credential isolation.

### Reliability and Compatibility

- Reuse the packaged noVNC 1.6-compatible input APIs and preserve physical keyboard, mouse, touch,
  canvas scaling, cancellation, expiry, and teardown behavior.
- Kiosk/app-like Chromium launch must be smoke-tested in the deployed Linux/Xvfb environment and
  must not create an untracked extra page or weaken the Booking.com navigation boundary.
- Construction must begin with a container compatibility spike for Chromium kiosk behavior and the
  installed noVNC input modules. `--app=<url>` is not acceptable unless Playwright proves it owns
  the sole page; if no controlled chrome-free mode works, stop and report the unmet requirement.
- Because the Docker build currently obtains noVNC from the distribution package, startup/build
  verification must fail safely when the required RFB, Keyboard, keysym, or keysym-definition
  modules are missing. API compatibility is covered by the browser fixture and remains part of the
  live Linux/Xvfb pre-deployment smoke gate.
- Input controls must be idempotent across repeated show/hide actions and remain disabled when no
  usable RFB connection exists.
- Automated coverage must include touch/platform fallbacks, key translation, buffer clearing,
  lifecycle cleanup, CSP preservation, and desktop regressions.
- Production acceptance requires real Telegram testing on at least one Android phone, one iPhone or
  iPad, and Telegram Desktop.

### Accessibility and Usability

- Every viewer control has visible text or an accessible name, an observable disabled/active state,
  and a minimum 44-by-44 CSS-pixel touch target.
- Instructions must use plain language and never ask users to send a Booking.com password in chat.
- Color is not the only signal for keyboard, connection, error, or terminal state.

### Performance

- Keystrokes are forwarded locally to the existing RFB object without polling or HTTP round trips.
- Platform discovery and input UI must not create another browser, VNC, or WebSocket connection.
- Viewer resizing must preserve the existing remote session and avoid page reloads.

## Constraints

- The remote browser remains Linux Chromium under Xvfb with a configured Pixel-class Android
  Playwright context; an Android emulator or native Booking.com app is out of scope.
- A remote canvas cannot reliably reveal whether the user tapped a text field. Software-keyboard
  activation therefore remains an explicit user action.
- Same-user abandoned-viewer reclamation must preserve the single global browser lease. The most
  recent same-user `/connect` is authoritative and may replace that user's current nonterminal
  attempt immediately.
- No new runtime dependency, JavaScript build tool, or public service is introduced.
- The final implementation must stay inside the current stdlib gateway, packaged noVNC modules, and
  existing remote-auth lifecycle.
- Commit, push, merge, and production deployment require separate explicit approval after
  construction review.

## Assumptions and Decisions

- The product owner identified lack of a mobile software keyboard as the blocking usability defect
  and approved a device-aware viewer fix.
- The current Android-emulated Booking.com page is the correct server-side price context even when
  the outer Linux Chromium window looks desktop-like.
- Telegram platform information is useful for presentation but touch capability detection is the
  more robust input-mode signal.
- The smallest robust approach is to adapt noVNC's existing mobile input-diff model around a
  password-semantic capture input rather than expose its full generic control panel or build an
  Android emulator.

## Scope Exclusions

- Native Android/iOS browser chrome, Booking.com native-app pricing, federated provider login, or
  device-local cookie extraction. The app-like Chromium surface removes misleading desktop chrome
  but is not a native mobile browser.
- Automatic inspection of Booking.com's remote DOM from the Mini App viewer.
- Password managers, credential autofill, clipboard paste, file transfer, or browser history UI.
- Concurrent remote browsers, changes to the global lease's exclusivity, authentication timeout, or
  per-user session storage.

## Open Questions

No blocking product questions remain for Inception. Real-device acceptance may reveal platform-
specific keyboard quirks; those must be resolved inside this intent before production deployment.
