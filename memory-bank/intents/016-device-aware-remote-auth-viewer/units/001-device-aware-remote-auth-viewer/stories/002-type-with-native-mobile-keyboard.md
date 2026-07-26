---
id: 002-type-with-native-mobile-keyboard
unit: 001-device-aware-remote-auth-viewer
intent: 016-device-aware-remote-auth-viewer
status: complete
priority: must
created: 2026-07-26T22:14:47.000Z
assigned_bolt: 030-device-aware-remote-auth-viewer
implemented: true
---

# Story: 002-type-with-native-mobile-keyboard

## User Story

**As a** phone or tablet user without a physical keyboard
**I want** to open my native keyboard and send text and navigation keys to Booking.com
**So that** I can complete direct login entirely from Telegram.

## Acceptance Criteria

- [ ] **Given** RFB is connected, **When** I tap `Keyboard`, **Then** a local hidden input receives
      focus during that user gesture, exposes password semantics to accessibility/IME APIs, and the
      device software keyboard opens. **Operations gate**: native Android/iOS keyboard acceptance
      remains pending.
- [x] **Given** keyboard mode is active, **When** I type ordinary or supported Unicode characters,
      **Then** equivalent RFB key events reach the focused remote field.
- [x] **Given** keyboard mode is active, **When** I erase text, **Then** noVNC-compatible Backspace
      events reach the remote field even on Android keyboards with incomplete hardware key events.
- [x] **Given** the input dock is visible, **When** I tap `Next` or `Enter`, **Then** Tab or Return is
      sent through the active RFB session.
- [x] **Given** keyboard mode is open, **When** I tap `Hide keyboard`, **Then** the local input blurs,
      its transient buffer is reset, and the RFB session stays connected.
- [x] **Given** the keyboard is already open or closed, **When** I repeat the same action, **Then**
      state remains correct without duplicated input or an exception.

## Technical Notes

- Adapt the installed noVNC 1.6 `Keyboard`, keysym, and input-diff behavior around a visually hidden
  password-semantic input, and prove that element choice on real Android and iOS before implementation.
- Disable autocapitalization, autocomplete, and spellcheck where the WebView respects those hints.
- Do not introduce clipboard paste or a generic noVNC control panel.

## Dependencies

### Requires

- 001-present-device-adaptive-viewer

### Enables

- 004-preserve-credential-and-desktop-safety

## Edge Cases

| Scenario | Expected Behavior |
|----------|-------------------|
| Android emits key code 229 | Input-diff fallback still forwards text and backspace |
| Keyboard autocorrection changes buffered text | Diff logic sends corresponding backspaces and replacement characters |
| Repeated show/hide cycles | Exactly one active input bridge remains attached |
| Unsupported character | Viewer fails safely without posting or persisting the buffer |
| Device IME exposes current composition | BookSaver UI never echoes it; buffer clears immediately after commit |

## Out of Scope

- Password-manager integration, autofill, clipboard synchronization, or text composition guarantees
  beyond installed noVNC support.
- Automatically determining which remote pixel is a text field.
