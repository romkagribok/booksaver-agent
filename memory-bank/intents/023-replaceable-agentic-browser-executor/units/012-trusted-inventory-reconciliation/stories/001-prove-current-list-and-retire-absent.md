---
id: 001-prove-current-list-and-retire-absent
unit: 012-trusted-inventory-reconciliation
intent: 023-replaceable-agentic-browser-executor
status: complete
priority: must
created: "2026-09-19T22:04:01Z"
assigned_bolt: 077-trusted-inventory-reconciliation
implemented: true
---

# US-192: Prove current-list coverage and retire absent reservations

As a user, I want reservations no longer on my current Booking.com list to stop appearing as active after a complete refresh.

## Acceptance criteria

- A code-owned caller/run/session-bound proof establishes the current active scope; provider completion
  claims, visited counts, missing next links and saved-row matches cannot manufacture authority.
- Prove root exhaustion and exact group membership, resolve every active identity, reject truncation,
  conflicting/unknown status, unresolved work, membership changes and final authentication/safety failures.
- With a validated proof, atomically reconcile positive observations and retire absent saved UPCOMING
  or CURRENT rows only in the covered caller/scope. Preserve history and stop stale monitoring/choices.
- Without proof, preserve unseen rows and accept only valid positives. Empty roots/groups require the
  same recognized scope/exhaustion proof; zero results alone are never absence evidence.
- Do not rewrite saved CANCELLED, COMPLETED or UNKNOWN rows merely because they are absent from Active.
- Replay/mismatched proof and any persistence conflict cannot partially retire rows or affect another caller.
