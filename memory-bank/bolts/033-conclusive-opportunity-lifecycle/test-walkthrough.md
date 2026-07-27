---
stage: test
bolt: 033-conclusive-opportunity-lifecycle
created: 2026-07-27T02:40:04Z
updated: 2026-07-27T02:46:10Z
---

# Test Report: Conclusive Opportunity Lifecycle

## Summary

- **Focused lifecycle tests**: 125 passed
- **Full repository tests**: 937 passed
- **Ruff**: Clean across `src` and `tests`
- **mypy**: Clean across 94 source files
- **Coverage**: Repository does not configure a coverage threshold

## Test Files

- [x] `tests/integration/test_savings_repo.py` - Conclusive ordering, preservation, invalidation,
      restoration, history, malformed rows, and two-write gap.
- [x] `tests/integration/test_rebook_repos.py` - Atomic session acceptance and rejection.
- [x] `tests/integration/test_user_scoping.py` - Owned current-opportunity isolation.
- [x] `tests/unit/rebook/test_rebook_service.py` - Shared service currentness and race rejection.
- [x] `tests/unit/telegram/test_rebook_gate.py` - Picker, direct ID, callback, and race behavior.
- [x] `tests/unit/savings/test_pipeline.py` - Positive, non-saving, failure, and notification pipeline
      behavior.

## Acceptance Criteria Validation

- ✅ **Technical failures preserve prior opportunity**: Every failure code except
  `NO_EQUIVALENT_OFFER` is covered parametrically.
- ✅ **Smaller saving remains actionable**: A newer price below baseline replaces the old quote.
- ✅ **Successful non-saving invalidates**: A success without a savings row produces no current
  choice.
- ✅ **No equivalent invalidates**: The semantic failure replaces prior market state.
- ✅ **Invalidation is booking-scoped**: A conclusive result for one booking leaves another
  booking's current opportunity unchanged.
- ✅ **Technical failure cannot revive invalidated history**: Explicit sequence coverage passes.
- ✅ **Later positive restores actionability**: The latest positive check becomes current.
- ✅ **Atomic guard agrees**: Session insert uses the same conclusive-current query.
- ✅ **Callback race stays truthful**: A conclusive update between callback preflight and session
  insertion produces only a currentness-check notice followed by rejection, with no optimistic
  picker edit, session, or confirmation.
- ✅ **Retained evidence stays transparent**: Telegram shows the original successful verification
  time and explains that technical failures do not update it.
- ✅ **History and ownership remain intact**: Historical readers and user scoping pass.
- ✅ **No migration or dependency**: Existing schema and dependency set are unchanged.

## Issues Found

None remaining. The design intentionally creates a short fail-closed window between persistence of a
new successful check and its positive opportunity row; the old quote is hidden during that window.

## Notes

Real Telegram testing is still the final environment acceptance step after a later approved
deployment. No deployment was performed in this bolt.
