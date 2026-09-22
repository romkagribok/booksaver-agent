---
id: 003-qualify-session-recovery
unit: 001-session-continuity
intent: 025-session-continuity-and-paste
status: complete
priority: must
created: "2026-09-20T20:04:41Z"
assigned_bolt: 078-session-continuity
implemented: true
---

# US-197: Qualify legacy recovery and session races

## Acceptance criteria

Legacy ACTIVE local expiry may enter verification-only recovery; no automatic READY; revocation, disconnect, newer revision, purge and explicit reauth remain protected. Test transient/signed-out classifications and caller isolation.

The complete acceptance contract is Intent025 requirements; this story does not relax that contract.
