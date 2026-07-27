---
stage: test
bolt: 032-current-rebook-opportunities
created: 2026-07-27T02:22:20Z
---

## Test Report: Current Rebook Opportunities

### Summary

- **Focused tests**: 73/73 passed
- **Full tests**: 909/909 passed
- **Ruff**: Clean across `src` and `tests`
- **mypy**: Clean across 94 source files
- **AI-DLC**: Artifact validation and status integrity clean before completion

### Test Files

- [x] `tests/integration/test_savings_repo.py` - Current grouping, ordering, insertion ties,
  archived filtering, and historical retention.
- [x] `tests/integration/test_rebook_repos.py` - Atomic stale rejection and current session insert.
- [x] `tests/integration/test_user_scoping.py` - Current-opportunity isolation by owner.
- [x] `tests/unit/rebook/test_rebook_service.py` - Pre-existing stale IDs and atomic-insert races
  create no session, prompt, event, or navigation.
- [x] `tests/unit/telegram/test_rebook_gate.py` - One button per booking, multiple-booking order,
  stale commands/callbacks, and an injected preflight-to-worker race.
- [x] Existing pipeline, callback, propagation, privacy, booking-management, and CLI tests - Full
  regression coverage.

### Acceptance Criteria Validation

- ✅ **One current choice per booking**: Repeated positive checks collapse to the newest stored row.
- ✅ **Different bookings remain choices**: Each active owned booking contributes at most one
  newest-first button.
- ✅ **Deterministic ties**: Equal validation timestamps use SQLite insertion order.
- ✅ **Inactive and foreign data hidden**: Active status and owner scope are query constraints.
- ✅ **Old UI cannot act**: Stale commands and callbacks receive `/rebook` guidance.
- ✅ **Race-safe session creation**: Immediate SQLite transaction makes currentness validation and
  session insert atomic.
- ✅ **No partial action**: A stale race creates no session, audit event, confirmation, or
  navigation.
- ✅ **Audit retained**: Historical list methods and rows remain unchanged.
- ✅ **Human boundary retained**: No cancel, reservation, payment, or final booking automation was
  added.

### Issues Found

Independent review identified and construction corrected:

- A non-atomic read-then-insert freshness window.
- Per-booking label lookup in the Telegram picker.
- Missing injected-race coverage.
- Test-double timestamp ties that did not model SQLite insertion order.

### Notes

The newest stored positive result is not a live-price guarantee. Automatic rechecking or
invalidation after later failed/non-saving checks remains explicitly outside this intent.
