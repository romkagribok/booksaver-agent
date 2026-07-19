---
id: 005-preserve-shared-check-pipeline
unit: 001-currency-alignment-recovery
intent: 008-currency-aligned-price-checks
status: ready
priority: must
created: 2026-07-19T00:32:13Z
assigned_bolt: 020-currency-alignment-recovery
implemented: false
---

# Story: Preserve the Shared Check Pipeline and Safety Gates

**Global story ID**: US-061

## User Story

**As a** BookSaver user
**I want** currency recovery to behave identically for scheduled and immediate checks
**So that** diagnostics, savings alerts, quotas, and safety do not depend on how a check started

## Acceptance Criteria

- [ ] Scheduled checks and `/checknow` execute the same currency-aligned monitor path.
- [ ] Same-currency checks and deterministic success add no unnecessary LLM call.
- [ ] Existing coordinator exclusivity, user quotas, timeout, agent caps, action guard, trace, history,
  savings, notification, and guided-rebook behavior remain effective.
- [ ] Existing no-availability, non-refundable, room-mismatch, and successful outcomes remain compatible.
- [ ] Focused and full automated/static quality gates pass without a database migration or dependency.

## Technical Notes

- Extend existing seams; do not add a second check orchestration path.
- Regression coverage should assert both recovered success and fail-closed unresolved mismatch.

## Dependencies

### Requires

- US-057 through US-060 and US-056 shared on-demand monitoring pipeline.

### Enables

- Safe VPS deployment and Telegram validation of the completed intent.

## Edge Cases

| Scenario | Expected Behavior |
|----------|-------------------|
| Scheduler owns browser during `/checknow` | Existing busy response remains authoritative |
| LLM quota is exhausted | Deterministic path remains usable; agent fallback cannot exceed quota |
| Same-currency cheaper refundable offer | Existing proactive savings alert still fires |

## Out of Scope

- Changing check scheduling, quota amounts, or rebook confirmation semantics.
