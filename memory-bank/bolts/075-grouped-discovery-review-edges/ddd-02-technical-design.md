---
stage: technical-design
bolt: 075-grouped-discovery-review-edges
created: 2026-09-14T19:34:14Z
status: complete
---

# Technical design and ADR analysis

Bugbot4008795226: filter status cards before canonical deduplication, so a longer Manage alias
cannot hide a card. Group readiness compares only status-card plus known-nonhotel counts to the
expected count using equality; under/overcounts wait boundedly and remain unresolved. Continue
to inspect unknown detail targets after the bounded wait rather than declaring completion.

Bugbot4008795233: retain initial root direct-detail count (unknown until observed) and count
verified groups. The runtime may return the existing informational EMPTY_UPCOMING outcome only
for zero active detail observations, all visible groups visited and count-verified, no root
direct detail targets, zero unresolved work, and positive inactive/nonhotel observations. Final
authentication and all guard checks precede this outcome. Unsupported active facts remain a
failure; they are never reclassified as empty. Pure known car groups may count without navigation.

ADR039 positive-only reconciliation, ADR040 interaction guard, and ADR048 bounded grouped reader
remain authoritative. No absence or monitoring authority, schema, new executor, time/cost/action
limit or booking interaction is introduced. Message wording must describe what was observed
without claiming account-wide completeness. No new ADR is required for this correction.

Tests cover delayed status cards behind duplicate aliases, over/undercounts, inactive-only and
car/inactive groups, root direct targets, unknown counts, contradictory statuses, unparseable
active details, and authentication/safety precedence. After the final source gate, build and
qualify a replacement image; the first image's passing results remain historical only.
