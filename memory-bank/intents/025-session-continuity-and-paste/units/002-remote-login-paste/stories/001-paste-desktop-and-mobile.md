---
id: 001-paste-desktop-and-mobile
unit: 002-remote-login-paste
intent: 025-session-continuity-and-paste
status: complete
priority: must
created: "2026-09-20T20:04:41Z"
assigned_bolt: 079-remote-login-paste
implemented: true
---

# US-198: Paste on desktop and mobile

## Acceptance criteria

Cmd/Ctrl+V and native paste insert exactly once; masked native fallback when clipboard access fails; preserve all printable ASCII characters/spaces and reject controls, oversize or unsupported Unicode before any insertion; no auto submit.

The complete acceptance contract is Intent025 requirements; this story does not relax that contract.

Measured limitation: full Unicode paste is unavailable on the packaged stack. The release
qualifies the core verification-code/ASCII email/password flow; unsupported text is never partly
inserted or silently altered. This limitation is disclosed, not marked as full-Unicode success.
