---
stage: test
bolt: 014-production-reliability
created: 2026-07-18T19:24:00Z
---

## Test Report: Production Reliability

### Summary

- **Focused tests**: 28/28 passed
- **Full tests**: 633/633 passed
- **Ruff**: clean across `src/`
- **Mypy**: clean across 72 source files
- **Coverage**: not separately measured; repository gate is the complete configured pytest suite

### Test Files

- [x] `tests/unit/monitor/test_search_journey.py` - Active query-first step order, trusted first
  navigation, zero homepage form operations, exact property matching, context mismatch, and wall/auth
  failure classification.
- [x] `tests/unit/monitor/test_search_journey_query.py` - Persisted property/date/occupancy query
  construction, URL encoding, and optional Booking.com destination identity.
- [x] `tests/unit/monitor/test_journey_escalation.py` - Guarded LLM recovery on results-page drift plus
  terminal give-up, budget, and bot-wall outcomes.
- [x] `tests/unit/monitor/test_monitor_agent_wiring.py` - Agent-assisted extraction marker and trace
  persistence for the five active journey steps.
- [x] `tests/unit/monitor/test_search_check_job.py` - Existing verified offer extraction and savings
  pipeline regression coverage.
- [x] `tests/unit/savings/test_savings_detection.py` - Existing baseline comparison and savings gates.

### Acceptance Criteria Validation

- ✅ **Trusted results entry**: The first active browser navigation contains persisted property,
  dates, adults, children, and rooms.
- ✅ **No homepage form operation**: Search-box, autocomplete, calendar, occupancy, submit, and
  overlay interactions are absent from the active journey and covered by regression tests.
- ✅ **Verified customer search preserved**: Exact result-card matching and fresh property-link
  opening remain mandatory.
- ✅ **Context verification preserved**: Wrong dates or occupancy fail before extraction.
- ✅ **Downstream LLM preserved**: A results-layout failure invokes the guarded agent, records agent
  assistance, and can continue only after the scripted postcondition verifies.
- ✅ **Fail-closed outcomes preserved**: Agent give-up, budget exhaustion, bot wall, wrong property,
  and wrong context remain failures.
- ✅ **Savings semantics preserved**: Existing room equivalence, refundability, currency, baseline
  comparison, and Telegram pipeline tests all pass unchanged.
- ✅ **No new dependency or architecture expansion**: Ruff and mypy pass; ADR-020 records the bounded
  amendment to ADR-013.

### Issues Found

The first full-suite run found four stale assertions that intentionally failed the removed
`fill_search` step or expected eight historical trace steps. They were updated to induce results-page
drift, verify downstream LLM recovery, and expect the five active steps. The second full run passed
633/633.

Obsolete calendar/form tests were removed because the associated implementation is no longer an
active product behavior. Query construction, step ordering, downstream recovery, and safety coverage
replace them.

### Notes

`git diff --check` passes. Untracked `.agents/` and `AGENTS.md` are pre-existing workspace inputs and
are intentionally outside this bolt.
