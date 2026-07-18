---
stage: test
bolt: 015-production-reliability
created: 2026-07-18T20:10:28Z
---

## Test Report: Property Availability Reliability

### Summary

- **Focused tests**: 37/37 passed
- **Full tests**: 641/641 passed
- **Ruff**: clean across `src/` and `tests/`
- **Mypy**: clean across 72 source files
- **Diff hygiene**: `git diff --check` passed
- **Dependencies/schema**: unchanged

### Acceptance Criteria Validation

- ✅ **Trusted fresh-property URL**: Persisted check-in/out, adults, children, and rooms overwrite
  stale/missing context on the exact result href; unrelated and duplicate opaque parameters survive.
- ✅ **Consent panel handled**: Decline/reject is attempted deterministically after results/property
  navigation; accept remains a bounded fallback and absence is a no-op.
- ✅ **Step responsibilities separated**: A safe Booking.com hotel page completes `open_property`
  without a room selector; complete URL context is checked before `read_room_table`.
- ✅ **Layout-tolerant readiness**: Known anchors or conservative price plus room/policy text reach the
  unchanged extraction pipeline.
- ✅ **Visual LLM recovery retained**: Missing rate readiness starts the guarded agent with a screenshot
  and the property-specific goal; semantic rates revealed by a safe action satisfy the postcondition.
- ✅ **Unavailable inventory terminates promptly**: Scripted and recovery-revealed sold-out text maps
  to `NO_EQUIVALENT_OFFER`; it cannot satisfy readiness even if a stale anchor exists.
- ✅ **Safety remains fail-closed**: External property hrefs, redirected wrong dates/occupancy,
  captchas, forbidden actions, and exhausted budgets cannot create a price or savings opportunity.
- ✅ **Production traces improved**: Agent actions include the observed target label beside ephemeral
  refs, while existing trace redaction remains active.

### Regression Files

- `tests/unit/monitor/test_search_journey.py`
- `tests/unit/monitor/test_journey_escalation.py`
- `tests/unit/monitor/test_trace.py`
- Full configured pytest suite, including offer selection, savings, Telegram, persistence, and agent
  guard/budget coverage.

### Commands and Results

```text
python3 -m pytest tests/unit/monitor/test_search_journey.py \
  tests/unit/monitor/test_journey_escalation.py \
  tests/unit/monitor/test_trace.py -q
37 passed

python3 -m pytest -q
641 passed

python3 -m ruff check src/ tests/
All checks passed!

python3 -m mypy src/
Success: no issues found in 72 source files
```

### Issues Found During Test

The implementation audit tightened readiness so captcha and explicit no-availability text always
override legacy anchors. It also preserved duplicate opaque result-link parameters and removed the
last calendar-specific retry instruction. Focused and full verification passed after those changes.

### Remaining Verification

Automated verification cannot assert Booking.com's current live DOM from the developer environment.
After final AI-DLC completion and git delivery, the operator should rebuild the VPS container and run
one Telegram check. The expected trace is `submit_search` → `locate_property` → `open_property` →
`verify_context` → `read_room_table`, followed by existing offer extraction or an explicit closed
availability/failure outcome.

Pre-existing untracked `.agents/` and `AGENTS.md` remain outside this bolt.
