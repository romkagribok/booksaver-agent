---
stage: implement
bolt: 020-currency-alignment-recovery
created: 2026-07-19T00:57:32Z
---

# Implementation Walkthrough: Currency Alignment Recovery

## Summary

Implemented fail-closed currency alignment in the existing Booking.com search monitor. Every search
and fresh property URL now requests the booking baseline currency. If rendered, otherwise-eligible
refundable offers still use another currency, the monitor attempts the visible currency preference
deterministically, falls back to the existing guarded browser agent when needed, and repeats the full
verified journey exactly once under the original check budget.

## Delivered Changes

- Trusted navigation context
  - Adds `selected_currency=<baseline ISO code>` to generated search-results URLs.
  - Replaces stale/conflicting currency values on fresh result-card property links while preserving
    opaque Booking.com query parameters, dates, and occupancy.
- Rendered offer evidence
  - Exposes candidates rejected only after passing refundability, room, and confidence gates and then
    failing the same-currency invariant.
  - Keeps every non-currency exclusion reason unchanged.
- Bounded recovery
  - Uses known header currency controls first and verifies the visible selected currency.
  - Uses `BrowserAgent` only when scripted controls are unavailable or unverifiable; its enumerated
    element references, action guard, screenshot tiers, step cap, LLM-call cap, and timeout remain in
    force.
  - Re-enters the complete results → exact property → verified context → room/rate journey once, then
    trusts only the newly rendered candidate currency.
- Failure and trace semantics
  - Adds `currency_mismatch` as a dedicated terminal failure when currency cannot be aligned.
  - Records requested/observed currencies, scripted/agent method, and final verification in the check
    trace.
  - Reuses `/checknow`'s existing generic completion transport, so Telegram receives the actionable
    failure detail and check ID without a second execution path.

## Safety and Reliability Notes

- No FX conversion, baseline mutation, or comparison between unlike currencies exists.
- The normal same-currency `Money`/offer-selection/savings gates remain authoritative after recovery.
- Recovery is triggered only by an otherwise-equivalent, positively refundable currency mismatch.
- There is no recursive retry, new browser concurrency, schema migration, runtime dependency, public
  bot behavior, or autonomous reservation action.
- Scheduled checks and `/checknow` continue through the same coordinator and monitor.

## Implementation Verification

- Focused currency/journey/trace/Telegram suite: 73 tests passed.
- Complete regression suite: 721 tests passed.
- Ruff passed for `src/` and `tests/`.
- mypy passed across 77 source files.
- `git diff --check` passed.
