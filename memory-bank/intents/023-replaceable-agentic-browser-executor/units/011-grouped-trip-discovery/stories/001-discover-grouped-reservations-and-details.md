---
id: 001-discover-grouped-reservations-and-details
unit: 011-grouped-trip-discovery
intent: 023-replaceable-agentic-browser-executor
status: complete
priority: must
created: "2026-09-13T16:10:04Z"
assigned_bolt: 074-grouped-trip-discovery
implemented: true
---

# US-187: Discover every grouped reservation and detail

As a user with several reservations grouped into trips, I want BookSaver to inspect the groups,
reservations, and necessary details so a first accepted record does not hide additional bookings.

## Acceptance Criteria

- Observe the actual grouped-trip structure and identify each reachable reservation/detail target
  in the admitted caller scope; do not equate one trip card with one reservation.
- Retrying a partially saved reservation must revisit required details. Restrict the processed
  semantic-match shortcut to already-eligible complete saved records, while retaining all caller
  confirmation hints for matching. Partial cached identities cannot make missing facts permanent.
- Continue bounded read-only discovery after the first accepted positive while relevant reachable
  groups, reservation pages, or required detail views remain unexplored.
- Maintain code-owned, bounded coverage evidence distinguishing observed, visited, accepted,
  rejected, and unresolved work. Agent success prose or row counts alone cannot prove coverage.
- Guarded destinations/actions, authentication, caller binding, runtime limits, and cancellation
  retain failure precedence. Exhausted budgets or ambiguous coverage produce an honest partial
  result; no unbounded retry or same-job fallback is introduced.
- Preserve validated positive records without authorizing absence-based deletion of saved rows.
- Diagnostics remain content-free/allowlisted and do not disclose raw reservation identifiers,
  authenticated page content, credentials, session data, or model reasoning.

## Design dependencies

Concrete grouped-page diagnosis from the main investigation; existing inventory contracts and
positive-only reconciliation. Final traversal/evidence representation is intentionally undecided.
