---
id: ADR-059
status: accepted
created: 2026-11-03T00:49:01Z
bolt: 093-reservation-change-sync
amends: ADR-058
---

# ADR-059: Code-read reservation changes replace saved facts

## Context

Saved reservation facts have been authoritative since agentic inventory (ADR-039, ADR-048), to keep
model output from overwriting them. Intent 019 FR-5 requires changed dates to update the same
reservation. A real date change failed every sync with `persistence_conflict`, stopping its checks.

## Decision

Extend ADR-058's provenance rule from the total to stay, room, occupancy and refund facts. Facts
from BookSaver's code-owned confirmation parser, for the same confirmation and hotel with both dates
present, replace saved ones. Provider-submitted facts still fail closed. When dates, room or
occupancy change, dependent facts not re-read are cleared; a missing total makes the reservation
ineligible until verified, so no check or alert uses the old total. A converted breakdown may prove
a printed booked-currency total includes tax; BookSaver stores only the printed total.

## Consequences

- Monitoring follows a changed reservation with no manual step.
- A parser defect could now change saved facts. It is bounded by the matching confirmation and hotel
  and by the parser's fail-closed shapes.
- A hold runs no price checks. The stall notice (FR-7) makes a long hold visible.

## Alternatives

- Ask the user to confirm each change: adds a manual step the sync-only design removed.
- Keep checking during a hold: needs a nullable baseline and yields nothing comparable.
