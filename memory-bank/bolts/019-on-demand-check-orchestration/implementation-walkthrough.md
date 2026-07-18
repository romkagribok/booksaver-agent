---
stage: implement
bolt: 019-on-demand-check-orchestration
created: 2026-07-18T23:48:00Z
---

# Implementation Walkthrough: On-Demand Check Orchestration

## Summary

Implemented `/checknow` and replaced the scheduler-only check closure with a daemon-lifetime shared
coordinator. Scheduled and immediate requests now use one non-blocking browser gate, thread-safe daily
check and actual-LLM counters, the same monitor/session/trace/history/failure path, and the same
savings/notifier pipeline.

## Delivered Changes

- `daemon/check_coordinator.py`
  - Serializes scheduled/manual work and rejects overlap without queuing.
  - Runs admitted manual work on a shutdown-aware daemon thread.
  - Re-resolves active user, booking ownership/status before execution and completion disclosure.
  - Reserves shared check allowance, caps per-check LLM use to the shared remaining daily allowance,
    and selects DOM/scripted-only mode at zero remaining LLM calls.
  - Preserves normal monitor results, trace/history, savings evaluation, alerts, cap notices, and
    invalid personal-key notices.
- `telegram/check_now.py`, gateway, and command catalog
  - Adds native/help discovery, caller-owned active booking picker, exact/unique-prefix shortcut,
    callback handling, immediate accepted/busy/stopping responses, and concise background results.
- Monitor and limits
  - Exposes actual calls consumed by the most recent check budget and supports explicit DOM-only mode.
  - Makes daily counters synchronized with atomic bounded reservation.
  - Clips fair scheduled plans to remaining quota and identifies only excess bookings as skipped.
  - Corrects `AgentBudget` so an over-cap attempted call is not counted as an actual LLM API call.
- Runtime wiring and documentation
  - `cmd_run` constructs one coordinator and injects it into scheduler and Telegram gateway.
  - README/runbook document operator behavior; ADR-021 and system architecture make the shared boundary
    authoritative.

## Security and Reliability Notes

- Selection, callback, worker start, and completion do not trust a Telegram payload as ownership.
- One global gate prevents duplicate/concurrent browser work even across scheduler/Telegram threads.
- Browser startup failures become persisted concise check failures after allowance reservation.
- Background completion sends use the now-thread-safe outbound message rate limiter.
- No schema, dependency, process, second scheduler, autonomous booking action, or public-bot mode was
  introduced.

## Implementation Verification

- Focused Ruff and mypy passed during implementation.
- 67 initial affected tests passed, followed by expanded coordinator/Telegram/monitor coverage.
- Full pre-walkthrough regression run passed 709 tests; final expanded run is recorded in the Test
  walkthrough.
