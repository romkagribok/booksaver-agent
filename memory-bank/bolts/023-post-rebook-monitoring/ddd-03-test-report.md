---
unit: 001-post-rebook-monitoring
bolt: 023-post-rebook-monitoring
stage: test
status: complete
updated: 2026-07-19T20:23:12Z
---

# Test Report — Post-Rebook Monitoring

## Summary

- `python3 -m ruff check src/ tests/` — clean.
- `python3 -m mypy src/` — clean across 81 source files.
- `python3 -m pytest -q` — **788 passed, 0 failed**.
- Focused post-rebook and Telegram rebook regression run — **55 passed**.
- New bolt coverage — **25 tests**: 8 domain/application, 9 persistence, and 8 Telegram
  reconciliation/dialog tests.

## Acceptance Criteria Validation

### US-072 — Collect actual replacement facts

- Replacement facts dialog starts only after the replacement handoff outcome is reported completed.
- Confirmation, actual `Money`, and an HTTPS Booking.com `/hotel/` URL are validated; a known source
  property path must match and tracking/session query parameters are stripped.
- Each accepted answer appears in the next prompt, and an explicit final `yes` is required.
- Tests prove the stored baseline is the entered checkout total rather than the detected live offer.

### US-073 — Propagate monitored replacement atomically

- The stable BookSaver booking ID is updated in place with the new confirmation, canonical property
  reference, actual baseline, and active status.
- Stay dates, room, refundability, occupancy, registration time, and ownership remain unchanged.
- User, ownership, terminal session, opportunity linkage, handoff, source snapshot, and confirmation
  uniqueness are revalidated inside `BEGIN IMMEDIATE` before mutation.
- Duplicate confirmation and missing/stale audit preconditions roll back without changing the booking,
  savings, or audit trail.

### US-074 — Reconcile partial outcomes safely

- Completed cancellation archives the source immediately; abandoned or unreported replacement then
  leaves no reservation monitored and tells the user how to recover.
- If neither handoff is completed, the original reservation and baseline remain active.
- A completed replacement starts actual-facts collection and can reactivate the stable booking after a
  reported completed cancellation.
- Final `no` preserves the already-established safe state; incomplete old cancellation produces a
  visible warning after replacement activation.

### US-075 — Preserve audit and invalidate stale savings

- Archive and activation delete stale savings and append one idempotent disposition event in the same
  transaction.
- Check history, traces, rebook sessions, and prior events remain attached to the stable booking ID.
- Repeated reconciliation returns an already-applied disposition without duplicate audit events.

### US-076 — Preserve access and visible completion

- Ownership and active-access checks occur before outcome collection and again in the write transaction.
- Revocation before final confirmation prevents replacement activation; foreign ownership and stale
  snapshots fail closed without leaking conflicting confirmation details.
- Outcome-button answers are visibly acknowledged, completion messages name the resulting monitoring
  state, and `/cancelflow` distinguishes archived-source from original-active recovery.

## Test Files

- `tests/unit/test_post_rebook.py` — canonical property validation and actual-facts propagation.
- `tests/integration/test_post_rebook_persistence.py` — atomic update/archive, stable history,
  idempotency, rollback, ownership, revocation, stale linkage, and confirmation conflicts.
- `tests/unit/telegram/test_rebook_propagation.py` — outcome matrix, dialog validation/final gate,
  visible acknowledgements, revocation, and follow-up integration.
- `tests/unit/telegram/test_rebook_gate.py` plus the full suite — unchanged guided-rebook state machine,
  Telegram gateway, persistence, monitor, notifications, and admin regressions remain green.

## Issues Found and Resolved

- The pre-existing outcome prompt recorded button taps only in the audit trail; it now removes the
  keyboard and visibly acknowledges `completed` or `abandoned`.
- Cancellation needed a durable safe state before the transient replacement-details dialog; archiving
  now commits first, so dialog cancellation or daemon restart cannot resume monitoring a cancelled stay.
- A second guided rebook could overlap a pending replacement-details dialog; the command now refuses
  until that dialog is completed or cancelled.

## Deliberate Boundaries

- No live Booking.com or Telegram network calls are made in tests.
- Confirmation ownership is user-reported at the current trust boundary; authenticated Booking.com
  receipt verification remains explicitly out of scope.
- No schema migration is required; the existing booking, savings, session, and append-only event tables
  support the transaction.

## Completion

- [x] All five story acceptance sets implemented and tested.
- [x] Full lint, type, and test quality gates pass.
- [x] No critical/high-severity issue remains open.
- [x] Product-owner review approved and the mandatory AI-DLC completion cascade succeeded.
