---
stage: plan
bolt: 020-currency-alignment-recovery
created: 2026-07-19T00:50:08Z
---

# Implementation Plan: Currency Alignment Recovery

## Objective

Make the booking baseline currency authoritative throughout Booking.com's results-to-property
journey, verify the actual currencies of rendered equivalent refundable offers, and execute at most
one deterministic-first/guarded-agent recovery before either returning a normal same-currency price
or an actionable fail-closed currency result.

## Prior Decisions Applied

- **ADR-013 / ADR-020**: Stay on the customer search path: trusted results query, exact result,
  fresh property href, verified context, room/rate evidence. Never use the registered property link or
  result-card headline as a price source.
- **ADR-014**: Persisted occupancy remains trusted context with no default.
- **ADR-015 / ADR-016**: Optional LLM fallback uses tiered observations, enumerated element refs,
  the bounded action vocabulary, and adapter-level destructive-action guards.
- **ADR-017**: Recovery and any second extraction consume the same per-check step, LLM-call, and
  wall-clock budget; no counter resets.
- **ADR-021**: Scheduled and `/checknow` work remain behind the one shared coordinator and monitor.

No new ADR is required: the bolt applies existing same-currency, search-journey, agent, budget, and
coordinator decisions without adding a technology or architectural pattern.

## Deliverables

1. Trusted currency navigation
   - Add `selected_currency=<baseline ISO code>` to generated search-results URLs.
   - Replace conflicting `selected_currency` values in fresh property result links.
   - Preserve all opaque non-context parameters, exact dates, and occupancy.

2. Rendered-currency selection evidence
   - Expose the candidates whose first and only exclusion is currency mismatch.
   - Preserve original first-failing exclusion reasons for non-refundable, unknown-refundability,
     room-mismatch, and low-confidence candidates.

3. One bounded alignment cycle
   - On a currency-only mismatch, attempt Booking.com's visible currency preference through stable
     scripted selectors first.
   - If scripted interaction is unavailable or cannot verify the selected header preference, allow
     the existing guarded browser agent to select the requested baseline currency.
   - Add a stable `align_currency` journey/trace seam for scripted and agent-assisted evidence.
   - Re-run the complete trusted results-to-property journey and offer extraction at most once.

4. Fail-closed classification and diagnostics
   - Add a `currency_mismatch` check failure code for persistent currency-only mismatches.
   - Trace desired currency, sorted observed currencies, scripted/agent recovery outcome, and final
     rendered verification.
   - Keep the Telegram formatter generic; its existing failure path will send the new code and
     concise actionable detail with the check ID.

5. Regression proof
   - Extend URL, journey, offer-selection, monitor, trace, and Telegram tests.
   - Cover same-currency zero-recovery behavior, scripted recovery, guarded-agent recovery,
     persistent mismatch, mixed exclusion causes, no-agent mode, budget preservation, and one-cycle
     enforcement.

## Planned Source Changes

- `src/booksaver/domain/journey.py`: add the stable currency-alignment journey step.
- `src/booksaver/domain/check_result.py`: add currency-specific failure vocabulary.
- `src/booksaver/domain/offer.py`: expose currency-only exclusion candidates as typed evidence.
- `src/booksaver/domain/agent.py`: add a currency-alignment trace kind.
- `src/booksaver/monitor/search_journey.py`: protect `selected_currency`, operate/verify known currency
  controls, and provide an agent postcondition based on the current header preference.
- `src/booksaver/monitor/search_check_job.py`: isolate extraction, coordinate exactly one recovery,
  re-run the verified journey, and map terminal outcomes.
- `src/booksaver/monitor/trace.py`: record redacted currency-alignment lifecycle events.

## Planned Test Changes

- `tests/unit/monitor/test_search_journey_query.py`: baseline currency in trusted search query.
- `tests/unit/monitor/test_search_journey.py`: protected property currency plus scripted preference.
- `tests/unit/monitor/test_offer_selection.py`: currency-only evidence without reclassifying other gates.
- `tests/unit/monitor/test_search_check_job.py`: recovered success, agent fallback, persistent mismatch,
  no-agent behavior, one cycle, and shared budget accounting.
- `tests/unit/monitor/test_trace.py`: currency-alignment trace event.
- `tests/unit/telegram/test_check_now.py`: actionable currency failure reaches `/checknow` completion.
- `tests/unit/monitor/fakes.py`: narrowly script currency-control and refreshed-page behavior.

## Acceptance Criteria

- [ ] Search and property URLs request and protect the baseline ISO currency.
- [ ] The monitor trusts rendered candidate currency rather than request state.
- [ ] Only an otherwise-equivalent positively refundable mismatch starts recovery.
- [ ] Scripted preference is attempted before LLM use; normal checks add no LLM call.
- [ ] Agent fallback remains guarded, tiered, and within the original budget.
- [ ] One and only one refreshed journey/extraction cycle can occur.
- [ ] Recovered candidates return through unchanged selection/savings behavior.
- [ ] Persistent mismatch returns `currency_mismatch` with desired/observed/recovery detail.
- [ ] No FX conversion, baseline mutation, schema migration, dependency, or parallel check path exists.
- [ ] Focused tests, full pytest, Ruff, mypy, and diff checks pass.

## Live Verification and Rollback

- Build and test locally before GitHub delivery.
- On the VPS, preserve the current commit hash as the rollback target, fast-forward pull the reviewed
  branch, rebuild/restart only the `booksaver` Compose service, and verify startup plus container state.
- The user's Telegram `/checknow` against the reproduced USD booking is the production acceptance
  check. A rollback is `git checkout <previous-hash>` followed by the same Compose rebuild/restart if
  startup or smoke verification fails.
