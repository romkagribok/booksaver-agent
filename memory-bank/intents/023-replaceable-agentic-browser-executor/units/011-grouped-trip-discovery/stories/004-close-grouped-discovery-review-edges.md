---
id: 004-close-grouped-discovery-review-edges
unit: 011-grouped-trip-discovery
intent: 023-replaceable-agentic-browser-executor
status: complete
priority: must
created: "2026-09-14T19:34:14Z"
assigned_bolt: 075-grouped-discovery-review-edges
implemented: true
---

# US-190: Close grouped-discovery review edge cases

As a user, I want delayed reservation cards and finished trip groups handled accurately so a
duplicate link cannot hide a booking and finished stays are not reported as a loading failure.

## Acceptance criteria

- Only exact counts of unique explicit status cards and known non-hotels establish group readiness;
  aliases do not end the wait, and late cards are visited. Unknown targets remain inspectable.
- Informational inactive-only outcomes require all visited groups to have known corroborated
  counts, no direct root hotel targets, no active/unparseable detail work, zero unresolved work
  and positive inactive/nonhotel evidence. Conflicting statuses never establish inactivity.
- Final authentication and all safety checks still win; saved reservations are preserved without
  new absence authority. User wording reflects observed scope rather than global completeness.
- Targeted regressions and the repository quality gate pass. Review threads receive tested fixes
  or evidence-backed dispositions. Current-head Bugbot success and replacement-image Dev/Staging
  verification remain mandatory release gates before merge/promotion.
