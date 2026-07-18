---
stage: plan
bolt: 015-production-reliability
created: 2026-07-18T20:00:27Z
---

## Implementation Plan: Property Availability Reliability

### Objective

Turn the correctly loaded Booking.com property page into a bounded, context-safe availability and
rate interpretation flow without relying on two legacy room-table selectors.

### Deliverables

- Merge persisted date and complete occupancy context into the fresh result-card property href.
- Dismiss consent overlays after results and property navigation, preferring reject/decline.
- Make `open_property` verify page navigation rather than room-table presence.
- Verify check-in, check-out, adults, children, and rooms before rate interpretation.
- Make `read_room_table` accept known anchors or conservative semantic rate evidence, escalate
  screenshot-first when content is not ready, and recognize explicit no-availability text.
- Replace calendar-centric global agent instructions with step-appropriate general recovery guidance.
- Add regressions for overlay handling, URL context merge, step ordering, semantic rate readiness,
  downstream LLM recovery, and no-availability classification.
- Update AI-DLC artifacts and operational architecture notes.

### Dependencies

- Existing `SearchJourney`, `BrowserAgent`, `InteractiveBrowser`, room-table parser, and failure codes.
- ADR-015 through ADR-017 guarded/tiered agent behavior and hard budgets.
- ADR-020 query-driven search entry and fresh-property-link constraint.

### Technical Approach

Property navigation will normalize the fresh Booking.com result href and overwrite only trusted
search-context query keys. Consent dismissal will be a small best-effort scripted helper invoked after
navigation. `open_property` will stop after a safe property URL is established; `verify_context` will
then check all search parameters. `read_room_table` will own rate readiness: known selectors and
conservative price/room/policy text can prove readiness, explicit unavailable text produces a closed
domain failure, and otherwise the guarded agent receives a screenshot-first goal. The existing
extraction and savings pipeline remains the only producer/consumer of live prices.

### Acceptance Criteria

- [ ] Trusted context is present on the fresh property URL.
- [ ] Consent panels cannot cover the rate-recovery viewport.
- [ ] Correct property navigation succeeds without a room-table selector.
- [ ] All date and occupancy values are verified before extraction.
- [ ] Changed but text-readable rate layouts reach DOM/LLM extraction.
- [ ] Explicit unavailable inventory ends promptly and distinctly.
- [ ] The LLM remains bounded, screenshot-capable, and destructive-action guarded.
- [ ] No live price is accepted without existing equivalence/refundability rules.
- [ ] Full automated and static gates pass.

### Process Authorization

On 2026-07-18 the product owner explicitly authorized AI-DLC to progress autonomously through Plan,
Implement, and Test for this corrective bolt, with one consolidated human approval immediately before
official bolt completion. This plan records the otherwise-mandatory Plan checkpoint as pre-approved.
