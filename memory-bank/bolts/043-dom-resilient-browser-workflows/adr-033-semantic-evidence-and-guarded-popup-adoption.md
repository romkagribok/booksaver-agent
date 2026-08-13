---
bolt: 043-dom-resilient-browser-workflows
created: 2026-08-13T02:39:01Z
status: accepted
superseded_by:
---

# ADR-033: Semantic Evidence and Guarded Popup Adoption

## Context

The existing browser agent can find a changed control but still fail because postconditions re-run
the old selector. Missing selectors can be misreported as property absence, empty extraction becomes
generic failure, and renamed safe inventory controls are rejected by text allowlists. The browser
can observe a new popup but cannot safely adopt it. Across these paths, useful exact model or policy
reasons are often collapsed into generic outcomes.

## Decision

1. Let models return only allowlisted positive semantic observations grounded in the fresh current
   page. Code-owned verifiers compare those observations with trusted booking/session/domain inputs.
2. Models cannot establish absence, completeness, equivalence, refundability, identity, currency
   alignment, or action safety. Existing deterministic domain services remain authoritative.
3. Treat selector misses, unknown layouts, unverified traversal, empty/invalid extraction, and safe
   no-progress as ambiguity eligible for Sonnet and bounded Opus diagnosis.
4. Treat conclusive known business, safety, authentication, provider, budget, observation, time, and
   infrastructure outcomes as exact zero-call terminals.
5. Adopt at most one newly opened popup only after infrastructure verifies approved Booking.com
   origin, a step-relevant read-only route, and absence of protected/mutating state. Models cannot
   transfer control directly.
6. Carry one canonical typed terminal diagnosis through every browser, inventory, search,
   coordinator, audit, and caller-facing mapping; registered paths cannot fall through to generic
   `unknown`, `navigation_failed`, `extraction_failed`, or `gave_up`.

## Consequences

The system can survive selector/copy changes when visible semantic evidence still proves progress,
while preserving fail-closed domain truth. Popup-based Booking.com navigation becomes usable without
allowing arbitrary child pages. More workflow results must carry typed diagnoses, and semantic
schemas/verifiers require explicit maintenance as new DOM steps are added.

## Related

- **Stories**: US-135, US-136
- **ADRs**: ADR-015, ADR-016, ADR-025, ADR-027, ADR-028, ADR-030, ADR-031, ADR-032
