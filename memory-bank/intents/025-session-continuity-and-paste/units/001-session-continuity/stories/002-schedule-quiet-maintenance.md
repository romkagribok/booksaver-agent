---
id: 002-schedule-quiet-maintenance
unit: 001-session-continuity
intent: 025-session-continuity-and-paste
status: complete
priority: must
created: "2026-09-20T20:04:41Z"
assigned_bolt: 078-session-continuity
implemented: true
---

# US-196: Schedule quiet background maintenance

## Acceptance criteria

Daily maintenance without eligible bookings; single coordinator gate; no model calls; 60-second bound; durable retries 15m/1h/6h/24h and deduplicated reconnect after confirmed interaction requirement or 48h unsuccessful recovery.

The complete acceptance contract is Intent025 requirements; this story does not relax that contract.
