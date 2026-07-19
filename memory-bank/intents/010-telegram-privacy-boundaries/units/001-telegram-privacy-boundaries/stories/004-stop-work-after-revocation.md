---
id: 004-stop-work-after-revocation
unit: 001-telegram-privacy-boundaries
intent: 010-telegram-privacy-boundaries
status: complete
priority: must
created: 2026-07-19T02:34:19Z
assigned_bolt: 022-telegram-privacy-boundaries
implemented: true
---

# Story: Stop Work After Revocation

**Global story ID**: US-070

## User Story

**As the** bot owner
**I want** revocation to be honored at every queued, completing, and messaging boundary
**So that** a removed user cannot trigger new cost or receive later sensitive bot content

## Acceptance Criteria

- [ ] Scheduled plans reauthorize immediately before allowance reservation and browser work.
- [ ] Queued work for a newly revoked user starts no browser/LLM work and persists no cap result.
- [ ] Immediate checks reauthorize before work and completion and suppress post-revoke details/alerts.
- [ ] Already-running browser work may persist locally, but reauthorization suppresses later savings,
  notices, completion details, and alerts.
- [ ] Rebook workers reauthorize at start and before every prompt, confirmation, handoff, and final
  reply; confirmation waits terminate within a bounded interval after revocation and release the
  active-session guard.
- [ ] Cap and invalid-key notices require an active target; savings routing remains active-owner only.
- [ ] Access loss terminates safely without another user's fallback or a sensitive error message.

## Technical Notes

- Reauthorization must re-read current persistence state; do not trust a plan/session snapshot.
- Current browser work may finish safely if cancellation is impractical, but no later sensitive
  delivery may occur and no queued work may begin after revocation is observed.
- Keep the coordinator's one-browser serialization and rebook confirmation state machine intact.

## Dependencies

### Requires

- Bolt 019 shared check coordinator.
- Intent 003 notification routing and rebook gate.
- Intent 009 explicit revoked-user experience.

### Enables

- US-071 deterministic revocation race suite.

## Edge Cases

| Scenario | Expected Behavior |
|----------|-------------------|
| User revoked after scheduled plan creation | Their later queue item is skipped before cost |
| User revoked while `/checknow` browser runs | No sensitive completion or alert after recheck |
| User revoked while rebook confirmation waits | Pending prompt/session terminates without handoff |
| Invalid personal key discovered after revocation | No key notice is sent |

## Out of Scope

- Retroactively deleting retained user data; purge remains separate.
- Preemptively killing a browser process when safe delivery suppression is sufficient.
