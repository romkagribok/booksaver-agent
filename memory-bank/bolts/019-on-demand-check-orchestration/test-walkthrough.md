---
stage: test
bolt: 019-on-demand-check-orchestration
created: 2026-07-18T23:55:00Z
---

# Test Report: On-Demand Check Orchestration

## Summary

- **Focused tests**: 71/71 passed.
- **Full regression suite**: 713/713 passed in 5.75 seconds.
- **Coverage**: Not re-measured; behavioral coverage added at coordinator, monitor, Telegram adapter,
  catalog/gateway, and user-limit seams.
- **Lint/type/diff**: Ruff clean, mypy clean across 77 source files, `git diff --check` clean.

## Test Files

- [x] `tests/unit/daemon/test_check_coordinator.py` - background admission, global busy gate,
  worker/completion authorization, shutdown, manual/scheduled shared check limits, partial scheduled
  quota, daily LLM capping and DOM-only fallback, normal history/trace/savings pipeline reuse.
- [x] `tests/unit/telegram/test_check_now.py` - scoped picker, payload bound, typed unique prefix,
  non-disclosing foreign/short selectors, callback acknowledgement, busy response, and concise
  property/price/check completion.
- [x] `tests/unit/monitor/test_user_limits.py` - atomic quota reservation and correct remaining-quota
  plan/skipped partition.
- [x] `tests/unit/monitor/test_search_check_job.py` - actual LLM call reporting and explicit DOM-only
  mode without factory/client use.
- [x] Existing gateway, catalog, monitor-agent, persistence, savings, scheduler, lifecycle, and full
  project regressions.

## Acceptance Criteria Validation

- ✅ **US-052**: Catalog/help/native publication shares `/checknow`; picker and typed selectors are
  active-user scoped and non-disclosing.
- ✅ **US-053**: Browser work runs on a daemon worker; admission is immediate; worker and completion
  reauthorize; completion is concise; stop rejects new work.
- ✅ **US-054**: Scheduler and Telegram share one coordinator/non-blocking gate and one execution
  pipeline; overlap is skipped/refused and never queued.
- ✅ **US-055**: Atomic shared check counters prevent cap bypass/overshoot; actual LLM calls are
  recorded, capped to remaining allowance, and zero allowance selects DOM/scripted-only operation.
- ✅ **US-056**: Real monitor integration persisted ordinary check history and trace and produced a
  savings opportunity through the normal pipeline; owner/key notification wiring is shared.
- ✅ **Safety**: No second scheduler/browser path, schema/dependency, public mode, or autonomous
  reservation action was introduced.

## AI-DLC Validation

- The artifact validator reports **zero issues in Intent 007 or Bolt 019**.
- Its repository-wide result remains non-clean because of 38 pre-existing legacy errors: 34
  historical story `id`/filename mismatches and four Bolt 009 story references using old filenames.
- Status integrity reports only the same four pre-existing Bolt 009 references; Intent 007/Bolt 019
  introduce no status inconsistency.
- No validator `--fix` was used because it would rewrite completed historical artifacts outside this
  intent.

## Issues Found and Resolved

- The prior scheduler plan could exceed a user's remaining daily quota within one tick; fixed and
  regression-tested.
- `AgentBudget` counted the rejected over-cap attempt as an actual LLM call; corrected before wiring
  daily actual-call accounting.
- The outbound Telegram rate limiter was unsynchronized; protected for completion sends from the new
  worker thread.
- Browser startup exceptions after manual admission now create a persisted navigation failure.

## Final Gate

Implementation and testing are complete. Bolt 019 remains `in-progress` at the Test checkpoint and
must not be officially closed, committed, merged, or pushed until human approval.
