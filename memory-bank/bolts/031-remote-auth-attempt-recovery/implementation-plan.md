---
stage: plan
bolt: 031-remote-auth-attempt-recovery
created: 2026-07-26T23:00:45Z
---

## Implementation Plan: Remote Authentication Attempt Recovery

### Objective

Make a new same-user `/connect` immediately replace that user's abandoned remote-auth attempt,
including when Telegram never delivers a close event, without weakening cross-user privacy or the
single shared browser lease.

### Deliverables

- Serialized remote-auth creation and same-user replacement.
- Cancellation and bounded worker teardown outside the manager state lock.
- Atomic transfer of the already-held global browser gate from the old worker to its replacement.
- Specific teardown-timeout guidance with no second browser.
- Suppressed duplicate cancellation notification for internally replaced attempts.
- Race tests for owner replacement, cross-user denial, gate reservation, timeout cleanup, repeated
  replacement, and old viewer capabilities.

### Technical Approach

Add a create-serialization lock and a replacement reservation keyed to the old attempt ID. Under the
manager lock, verify ownership, mark a same-user attempt cancelled, signal its worker, and reserve
the browser gate. Wait for the worker only after releasing the manager lock.

When the old worker releases its active-attempt record, retain the locked browser gate if a matching
replacement reservation exists. The same `/connect` then starts its new worker using that retained
lease, leaving no gap in which a scheduled price check can steal it. On bounded timeout, clear the
reservation while the old worker still owns the gate so its normal cleanup releases exactly once.

Different-user requests retain the generic privacy-safe busy response. A price-check-owned gate
retains its separate short busy response. The newest same-user command is authoritative; serialized
duplicate commands may replace the immediately preceding attempt, but never run two browsers.

### Verification

- Deterministic unit tests with controllable multi-invocation runners.
- Existing capture/cancel serialization and purge cancellation regressions.
- Gateway browser test for best-effort pagehide cancellation and close-signal loss fallback.
- Ruff, mypy, full pytest suite, AI-DLC validators, and diff hygiene.

### Risks and Controls

- Gate double release: release decisions are made only under the manager lock and tied to the
  reserved attempt ID.
- Worker teardown delay: bounded wait returns precise retry guidance; it never starts a second
  browser.
- Cross-user takeover: ownership is checked before cancellation and no capability value is reused.
- Close event loss: correctness is manager-side and does not depend on WebView lifecycle delivery.
