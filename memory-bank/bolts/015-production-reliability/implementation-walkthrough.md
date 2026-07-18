---
stage: implement
bolt: 015-production-reliability
created: 2026-07-18T20:08:36Z
---

## Implementation Walkthrough: Property Availability Reliability

### Summary

BookSaver now treats safe property navigation, trusted-context verification, and availability/rate
readiness as separate steps. It dismisses Booking.com's consent panel deterministically and reserves
the screenshot-capable LLM for layouts whose read-only availability state cannot be proven by script.

### Completed Work

- [x] `src/booksaver/monitor/search_journey.py` - Merges trusted dates and complete occupancy into the
  fresh result-card href while preserving opaque parameters, rejects external property links,
  dismisses consent after navigation, and verifies the complete URL context.
- [x] `src/booksaver/monitor/search_journey.py` - Makes `open_property` prove only safe property
  navigation; makes `read_room_table` recognize known anchors, conservative semantic rate evidence,
  bot walls, and explicit unavailable inventory.
- [x] `src/booksaver/monitor/search_journey.py` - Sends unresolved rate readiness to screenshot-first
  guarded recovery and reclassifies an unavailable state revealed during recovery.
- [x] `src/booksaver/infrastructure/llm/anthropic_adapter.py` - Replaces calendar-specific global
  instructions with the current named-step goal and read-only property-availability guidance.
- [x] `src/booksaver/monitor/browser_agent.py` and `src/booksaver/monitor/trace.py` - Keep recovery
  prompts step-neutral and add visible target labels to agent-action traces so production references
  such as `e32` are diagnosable.
- [x] `tests/unit/monitor/` - Covers trusted URL merging, duplicate opaque parameters, consent
  dismissal, semantic rates without selectors, redirect/context mismatches, explicit unavailability,
  screenshot-first recovery, recovery-discovered unavailability, unsafe hrefs, and labeled traces.

### Key Decisions

- **Fresh href plus trusted context**: The link still comes from the exact live search result; only
  persisted search-context keys are authoritative and overwritten before navigation.
- **Deterministic consent control**: Decline/reject is preferred, with accept only as a fallback; no
  LLM call is spent deciding a consent button.
- **Semantic readiness is not extraction**: Conservative price plus room/policy text can allow the
  existing offer extractor to run, but the journey never emits or accepts a live price itself.
- **Unavailable inventory fails closed**: A sold-out response is a legitimate completed search
  outcome, mapped to `NO_EQUIVALENT_OFFER`, never treated as rate content or a reason to keep clicking.
- **Safety boundaries unchanged**: The adapter action guard, shared step/LLM/time budgets, exact
  property match, context verification, offer equivalence, refundability, and savings gates remain.

### Deviations from Plan

Agent-action trace labels were added during implementation audit because the production evidence used
opaque references (`e32`, `e94`) that could not identify what the model clicked. This is a compatible
diagnostic extension and does not change the action vocabulary or persistence schema.

### Dependencies Added

None.

### Focused Verification

The implementation-stage suite passed 37/37 focused tests and Ruff passed for every modified source
and test file. Full repository verification belongs to the Test stage.
