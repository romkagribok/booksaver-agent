---
id: 031-remote-auth-attempt-recovery
unit: 001-device-aware-remote-auth-viewer
intent: 016-device-aware-remote-auth-viewer
type: simple-construction-bolt
status: complete
stories:
  - 005-recover-from-abandoned-viewer
created: 2026-07-26T22:14:47.000Z
started: 2026-07-26T23:00:45.000Z
completed: "2026-07-26T23:03:21Z"
current_stage: null
stages_completed:
  - name: plan
    completed: 2026-07-26T23:00:45.000Z
    artifact: implementation-plan.md
  - name: implement
    completed: 2026-07-26T23:01:40.000Z
    artifact: implementation-walkthrough.md
  - name: test
    completed: 2026-07-26T23:02:46.000Z
    artifact: test-walkthrough.md
requires_bolts:
  - 026-remote-authentication-gateway
  - 030-device-aware-remote-auth-viewer
enables_bolts: []
requires_units: []
blocks: true
complexity:
  avg_complexity: 2
  avg_uncertainty: 2
  max_dependencies: 2
  testing_scope: 3
---

# Bolt: 031-remote-auth-attempt-recovery

## Overview

Add a separately reviewed lifecycle and concurrency correction for remote-auth viewers that close
without explicit cancellation.

## Objective

Let a follow-up same-user `/connect` immediately replace an abandoned attempt, with best-effort
close cancellation as an optimization, while preserving worker-owned teardown, capture/cancel
serialization, cross-user privacy, and the single global browser lease.

## Stories Included

- **005-recover-from-abandoned-viewer**: Recover from an abandoned viewer (Must)

## Bolt Type

**Type**: Simple Construction Bolt
**Definition**: `.specsmd/aidlc/templates/construction/bolt-types/simple-construction-bolt.md`

## Stages

- [x] **1. Plan**: Complete → `implementation-plan.md`
- [x] **2. Implement**: Complete → source, tests, and `implementation-walkthrough.md`
- [x] **3. Test**: Complete → `test-walkthrough.md`

## Planned Technical Approach

1. On a same-user `/connect`, mark that user's current nonterminal attempt cancelled under the
   manager lock and signal its worker without reading or reusing viewer capabilities.
2. Wait for worker teardown only outside the manager lock and only for a short bounded period.
3. If teardown releases the shared browser gate in time, start and return exactly one replacement
   attempt in the same `/connect` command.
4. If teardown remains active, return precise short retry guidance and never start a second browser.
5. Preserve the privacy-safe busy response for a different user's active attempt and the separate
   price-check/browser-gate contention response.
6. Add a conservative best-effort `pagehide` cancellation hook to the reviewed Bolt 030 viewer, never
   using `visibilitychange` as a correctness signal.
7. Prove close delivery, close loss, old-poll-after-cancel, capture-versus-reclaim, two same-user
   requests, bounded worker teardown, and different-user races.

## Dependencies

### Requires

- **026-remote-authentication-gateway**: active-attempt manager and worker-owned lease (Complete)
- **030-device-aware-remote-auth-viewer**: reviewed viewer lifecycle and unload integration point

### Enables

- Reliable repeat `/connect` attempts and production real-device acceptance.

## Success Criteria

- [x] Story 005 and all acceptance criteria are implemented.
- [x] Unload cancellation remains a best-effort optimization rather than the correctness boundary.
- [x] Only the owning Telegram user can cancel/reclaim their current attempt.
- [x] No flow starts two browsers, releases another user's lease, or revives a cancelled attempt.
- [x] Capture/cancel and worker teardown races have deterministic tests.
- [x] Existing price-check and remote-login browser leasing remains regression-free.
- [ ] Final product-owner merge review is complete.

## Execution Authorization

The product owner approved the stronger immediate-replacement requirement and authorized
uninterrupted construction through final pre-merge review. Git, merge, push, and deployment remain
held for final approval.
