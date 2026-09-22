---
stage: model
bolt: 079-remote-login-paste
created: 2026-09-20T20:05:16Z
---

# Explicit remote-login paste model

## Entities and aggregate

The remote-login viewer connection is the aggregate boundary: one authenticated RFB connection,
its connected/terminal state and monotonically invalidated input generation. A paste attempt belongs
to exactly that connection/generation and a trusted user gesture. Its transient text never becomes
application data, persistent state, a server HTTP payload or a remote clipboard value.

A masked native paste field holds only the current user-provided buffer until explicit Insert.
A clipboard read attempt may settle later; connection replacement, disconnect, cancellation,
finalization and teardown invalidate it irrevocably. No text is transferred to a later connection.

## Value objects and rules

- PasteText: bounded printable ASCII for the qualified release, preserving spaces exactly. Reject
  unsupported Unicode, oversized text and control characters/newlines before any insertion, without truncation,
  substitution or generating Enter/Tab/navigation keys.
- PasteOwner: exact RFB object and input generation. Every asynchronous continuation must match.
- PasteOutcome: sent, unavailable, invalid or cancelled; status text never includes submitted text.
- Send progress: each codepoint is sent at most once; no duplicate native paste/input/shortcut path.

## Services and events

ExplicitClipboardRead reads once only after a trusted Cmd/Ctrl+V or Paste click. NativePasteCapture
accepts text/plain from an explicit paste event. LiteralRemoteInput transmits through the existing
RFB keyboard channel after modifier release, preserving the selected remote field. PasteFinished
clears local text; ViewerTeardown cancels queued work, clears the field and discards pending reads.

No clipboard writes/polling, remote-to-local synchronization, automatic submission, new credentials
endpoint, telemetry or logging is introduced. US198 covers usable entry; US199 covers the transient
boundary and mocked versus exact-packaged verification distinction.

Qualification refinement: the original full-Unicode goal is not implemented on the packaged
x11vnc/Chromium stack. Fail-closed rejection preserves credentials; the accepted core clipboard
flow supports verification codes, ASCII emails/passwords and native fallback. No transport or
security boundary is relaxed to hide that limitation.
