---
id: 002-preserve-eligibility-and-distinguish-current-stays
unit: 011-grouped-trip-discovery
intent: 023-replaceable-agentic-browser-executor
status: complete
priority: must
created: "2026-09-13T16:10:04Z"
assigned_bolt: 074-grouped-trip-discovery
implemented: true
---

# US-188: Preserve strict eligibility and distinguish current stays

As a user, I want discovered reservations and their monitoring status explained accurately so
current stays or missing details do not appear as a failure or as price-check-ready bookings.

## Acceptance Criteria

- A first-time positively observed reservation with validated future dates and all qualifying
  facts must receive the same correct lifecycle, persisted projection, upcoming display, and
  monitoring eligibility as an equivalent saved-match reservation. Missing cached state cannot
  leave a valid new reservation UNKNOWN/not_upcoming. Accepted counts alone are not success.
- Lifecycle/date classification must use validated current evidence; cancelled, conflicting,
  date-less, or otherwise ambiguous records cannot gain eligibility through this correction.
- Classify current, upcoming, and completed observations according to existing stay-date policy;
  an active trip grouping alone cannot establish that every included reservation is upcoming.
- A saved upcoming stay may progress to current/completed, or current to completed, only when
  the same confirmation and unchanged complete dates corroborate that progression against trusted
  UTC observation time. Preserve financial facts, recalculate eligibility, and disable current/past
  monitoring projections. Other explicit conflicts remain rejected atomically.
- Details supporting reservation identity, room type, occupancy, booked total/currency, and explicit
  refundability must pass existing validation before monitoring eligibility is granted.
- English Booking property URL suffixes `.en-us`/`.en-gb` and the unsuffixed path may represent
  the same hotel only with unchanged country/slug, same allowlisted HTTPS host, no credentials
  or ports, and exact normalized visible-name agreement. All other price-query gates remain.
- Missing, conflicting, or unvisited required detail facts remain ineligible with plain explanations;
  group summaries, cached values, or a model's confidence cannot fill evidence gaps silently.
- Preserve accepted current-run positives and prior saved reservations when traversal is partial;
  neither an informational coverage result nor an empty filtered view establishes absence.
- User messages distinguish successfully observed current stays, upcoming reservations, accepted
  partial results, missing monitoring facts, and actual loading/authentication failures.
- Unfinished traversal does not imply full account success, and correctly ineligible/current
  observations are not mislabeled as browser failures.

## Dependencies

US-187 coverage/evidence outcomes and Unit 010's plain-language outcome handling. No relaxation of
refundable-only monitoring, equivalent all-in pricing, or current-run positive-evidence authority.

## Confirmed diagnostic evidence

Reviewer inspection found that the first-time identity path leaves lifecycle unknown, and the
optional fact submission set excludes lifecycle. A saved-match path supplies upcoming lifecycle.
Thus a new identity can carry valid future dates and complete qualifying facts while persisting
as UNKNOWN, becoming not_upcoming, and disappearing from the upcoming view. Regression acceptance
must follow the record through validation, persistence, display, and eligibility, not only executor
acceptance. The final repair design remains a construction decision.

Fresh caller candidate 16 completed navigation and validated six positives but the normal upcoming-to-current transition of an unchanged saved stay caused a persistence conflict and full rollback.
This establishes the need for the narrowly date-corroborated status progression above. It does not
justify overwriting booking terms or treating arbitrary source contradictions as safe updates.
