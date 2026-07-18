---
stage: plan
bolt: 014-production-reliability
created: 2026-07-18T18:57:24Z
---

## Implementation Plan: Production Reliability

### Objective

Remove Booking.com homepage form operation from the active check journey and navigate directly to the
existing trusted search-results query, preserving every downstream verification, LLM recovery,
offer-selection, and savings constraint.

### Deliverables

- Update `SearchJourney` so active execution starts with exact search-results navigation rather than
  `open_home`, overlay dismissal, and `fill_search`.
- Remove obsolete form-entry recovery/fallback branching and form-specific implementation that no
  longer participates in a check, while retaining historical trace enum compatibility where useful.
- Preserve results-card loading, exact property matching, fresh property-link navigation, requested
  context verification, room-table interpretation, bot-wall detection, and guarded agent escalation.
- Add regression tests proving homepage form methods are not called, trusted query parameters are
  used, downstream LLM recovery still activates, and mismatches still fail closed.
- Record an ADR amendment to ADR-013 describing query-driven search entry and update the decision
  index/system documentation accordingly.
- Produce implementation and test walkthroughs with focused/full verification evidence.

### Dependencies

- `_search_results_url(booking)`: existing trusted query constructor.
- `SearchJourney`: existing named-step coordinator and verification seams.
- `BrowserAgent`, `AgentBudget`, and `ActionGuard`: unchanged downstream recovery and safety controls.
- `SearchCheckJob`, room-table parser, LLM offer extractor, and savings pipeline: unchanged consumers.
- ADR-013 through ADR-017: existing price-source, observation, action-safety, and budget decisions.

### Technical Approach

The active journey will navigate first to Booking.com's `searchresults.html` URL constructed from the
persisted property name, check-in/check-out dates, adults, children, and rooms. It will continue
through exact result-card matching and the fresh property href returned by Booking.com; it will not
deep-link the registered property URL or treat a result-card price as savings evidence.

The homepage form path and its late exact-query fallback will be removed from active orchestration so
they cannot consume the shared wall-clock and LLM-call pool. Named downstream steps retain their
existing scripted-first, guarded-LLM-on-failure behavior. The implementation will fail closed whenever
property/context/equivalence checks cannot be proven.

### Acceptance Criteria

- [ ] A normal journey's first browser navigation is the trusted Booking.com search-results URL.
- [ ] No homepage search-box, calendar, autocomplete, occupancy, or submit interaction occurs.
- [ ] The query contains persisted property, dates, adults, children, and rooms.
- [ ] Exact property matching and fresh result-link opening remain mandatory.
- [ ] Dates and occupancy are verified before room offers enter extraction.
- [ ] Guarded LLM recovery remains reachable for results/property/room-page drift.
- [ ] Search-card prices and registered-property deep links are never used as the live price source.
- [ ] Bot walls, mismatches, missing availability/equivalent offers, and budget breaches fail closed.
- [ ] Focused tests, full pytest, Ruff, and mypy pass with no new dependency.

### Relevant Prior Decisions

- **ADR-013**: Retain Booking.com search results and fresh property-room-table pricing, but amend the
  original requirement to operate the homepage form.
- **ADR-015**: Preserve tiered text-to-screenshot observations on downstream escalation.
- **ADR-016**: Preserve bounded tool use and adapter-level destructive-action guard.
- **ADR-017**: Preserve the shared hard budget; this correction prevents a redundant step from
  exhausting it rather than increasing limits.

### ADR Assessment

An ADR amendment is required because ADR-013 explicitly says every check fills the homepage form and
permits no shortcut. The new decision will distinguish a Booking.com search-results query from the
rejected direct-property deep link: search results, exact-property selection, fresh property link,
context verification, and room-table extraction all remain mandatory.
