---
id: 002-guard-and-qualify-paste
unit: 002-remote-login-paste
intent: 025-session-continuity-and-paste
status: complete
priority: must
created: "2026-09-20T20:04:41Z"
assigned_bolt: 079-remote-login-paste
implemented: true
---

# US-199: Guard and qualify clipboard input

## Acceptance criteria

User-gesture-only, one-way RFB typing; no content logging/persistence/HTTP endpoints; clear text; ignore late results after teardown/session replacement. Test exact packaged remote stack and identify native Telegram acceptance separately.

The complete acceptance contract is Intent025 requirements; this story does not relax that contract.
