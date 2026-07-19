---
stage: test
bolt: 020-currency-alignment-recovery
created: 2026-07-19T00:57:32Z
---

# Test Report: Currency Alignment Recovery

## Summary

- **Focused tests**: 73/73 passed.
- **Full regression suite**: 721/721 passed in 5.89 seconds.
- **Lint/type/diff**: Ruff clean, mypy clean across 77 source files, `git diff --check` clean.
- **Dependencies/schema**: unchanged.

## Covered Behavior

- [x] Generated search URLs carry the booking baseline currency.
- [x] Fresh property links replace stale currency while preserving duplicate opaque parameters and
  all trusted stay/occupancy context.
- [x] Header preference selection is deterministic-first and must visibly verify the requested
  currency.
- [x] Only positively refundable, room-equivalent, confident candidates produce currency-only
  evidence; other exclusion reasons remain unchanged.
- [x] Scripted alignment can refresh the complete journey once and produce a same-currency success
  without an LLM call.
- [x] Selector drift can use the existing guarded agent and marks the result agent-assisted.
- [x] Persistent mismatch terminates after one refresh with `currency_mismatch` and no cross-currency
  comparison.
- [x] Missing agent support terminates safely and does not start an unverified refresh loop.
- [x] Currency alignment lifecycle events persist in the ordinary check trace.
- [x] `/checknow` sends actionable currency failure detail and the short check ID.
- [x] Existing session, navigation, extraction, savings, scheduler/coordinator, Telegram, and rebook
  regressions remain green.

## Acceptance Criteria Validation

- ✅ **US-057**: Baseline currency is authoritative in trusted search and property navigation.
- ✅ **US-058**: Rendered offer currency, not URL request state, controls selection eligibility.
- ✅ **US-059**: One deterministic-first/guarded-agent recovery uses the original budget and complete
  verified journey.
- ✅ **US-060**: Unresolved alignment fails closed with requested/observed/method evidence.
- ✅ **US-061**: Scheduled and on-demand checks retain one coordinator/monitor/savings/notification
  pipeline and all safety gates.

## AI-DLC Validation

- The mandatory bolt-completion script completed Bolt 020 and its five stories, unit, and intent.
- The artifact validator reports no issue in Intent 008 or Bolt 020. Its repository-wide result
  remains non-clean because of 38 pre-existing legacy issues: 34 historical story ID/filename
  mismatches and four Bolt 009 references using old filenames.
- Status integrity reports only those same four pre-existing Bolt 009 missing-reference
  inconsistencies; Intent 008/Bolt 020 introduces no inconsistency.
- No validator `--fix` was used because it would alter completed historical artifacts outside this
  approved intent.

## Final Gate

Implementation and automated verification are complete. The product owner continuously authorized
Plan → Implement → Test, commit/push, and VPS deployment on 2026-07-19T00:44:22Z; the approved bolt
may now be formally closed and delivered.
