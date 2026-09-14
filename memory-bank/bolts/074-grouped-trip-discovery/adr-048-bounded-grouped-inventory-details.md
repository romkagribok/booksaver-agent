---
adr: ADR-048
status: accepted
created: 2026-09-13T20:05:00Z
bolt: 074-grouped-trip-discovery
amends: ADR-039, ADR-044, ADR-047
depends_on: ADR-021, ADR-036, ADR-039
---

# ADR-048: Bounded Grouped Inventory Details

## Context

Fresh isolated inspection of an invited account confirmed trip-group navigation and mobile
confirmation pages that omit required booked-party and cancellation facts. The actual rendered
Desktop version link exposes the full confirmation. A six-accommodation scan needs approximately
29 metered actions; the previous inventory ceiling of 15 stops after roughly three details even
with zero model calls. Raising the global price-executor allowance or accepting partial money
facts would not address those failures safely.

## Decision

Within the existing Browser Use inventory episode, use a bounded code-owned worklist for the
qualified grouped layout and parse narrowly recognized rendered confirmation sections. Links
must be freshly resolved from the actual rendered page, including the real ancestry, and pass the
unchanged read-only guard. The desktop view action must preserve the same confirmation identity
and path and change only the observed presentation parameter. Source/focus, authentication,
dialog, destination, deadline, action and cost boundaries remain authoritative.

Never export session material from the grouped reader, including after returning to mobile.
Retain the original encrypted mobile session for later price execution; full confirmation
presentation is inventory-only. This amends ADR-047's blanket inventory presentation constraint,
not the mobile live-price product or remote-auth verification contract.

Inventory receives a separate typed maximum of 40 actions. Price retains an independently
validated maximum of 15. An inventory-bearing coordinator job has one cumulative allowance of
40; subsequent price requests are capped at 15 and the remaining cumulative allowance. The existing dollar, action and computer-input caps remain shared without reset. Each executor
request remains capped at 180 seconds. A combined inventory-and-price coordinator operation has
one absolute 360-second ceiling; an inventory-only operation retains 180 seconds. Each phase
receives a fixed deadline no later than 180 seconds from its admission or the remaining operation
deadline. Explicitly supplied lower limits are respected. No phase begins after shutdown is requested.

All extracted facts pass the existing typed mapper, identity/lifecycle validation, positive-only
reconciliation and eligibility rules. Unknown or contradictory money/occupancy/refundability stays
unqualified. No source URL with authentication material is persisted. Observed traversal counts
do not establish account completeness, absence, or eligibility.

## Consequences and alternatives

The recognized grouped layout avoids repeated model navigation decisions. Unsupported layouts and
unresolved details remain visible in qualification evidence and fail closed; no arbitrary model URL,
legacy adapter fallback, transaction power, new browser, schema or service is introduced. The
existing agent path remains for non-grouped accounts. Exact-caller and final-image qualification
are still required; this decision does not claim those checks have passed.

The user's explicit instruction to diagnose, implement, validate, merge and redeploy covers this
narrow read-only correction and its AI-DLC checkpoints. Mandatory review and release gates remain.

## Date-corroborated lifecycle progression

Actual-caller candidate 16 isolated a second persistence defect after navigation succeeded: the
same saved stay had naturally progressed from upcoming to current. The existing last-safe policy
must permit only forward lifecycle transitions corroborated by the same saved confirmation,
identical complete stay dates, and trusted observation date. Recalculate eligibility and disable
current/completed monitoring projections; preserve saved money/refund/occupancy facts and reject
all remaining explicit contradictions. This is not permission to overwrite reservation terms,
accept an arbitrary model status, or skip unrelated persistence errors.

## Combined operation time allocation (2026-09-14)

Normal invited-caller replay 19 loaded five active reservations across both trip groups, persisted
the observations, and qualified two stays. The following normal immediate check repeated inventory
under the same 180-second operation deadline and returned an agentic price timeout. Successful
inventory has required approximately 140 seconds, leaving only about 40 seconds for price execution.
This amends ADR-039 only for the combined operation wall-clock ceiling: two bounded capabilities
receive their own non-sliding, at-most-180-second phase deadlines within 360 seconds total. It does
not reset the shared cost/action/visual ledger or relax current-run inventory receipts. The existing
200-second shutdown grace relies on stopping between phases and bounding an active phase to 180
seconds; final-image shutdown verification remains required. A selected-reservation inventory
shortcut would change discovery coverage and needs separate evidence, so it is not introduced.

## English property URL representation

Caller replay 21 reached a price observation in 63,611 ms, but the exact same visible hotel name
was rejected because the trusted confirmation link ended in `.en-us.html` and Booking.com's
actual price page used `.html`. Treat only the known English `.en-us`/`.en-gb` suffixes as
presentation variants of an otherwise identical Booking hotel country/slug path. Both URLs must
use HTTPS, the same allowlisted Booking host and no credentials or ports for this equivalence.
Keep exact normalized visible-name agreement, country/slug identity, dates, occupancy, currency,
refundability and total-evidence checks unchanged. Unknown locale/path/host aliases still fail
closed. This is a canonical representation correction, not fuzzy property matching or authority
to substitute another hotel. Final live validation must prove the previously rejected observation
passes all remaining acceptance gates; no successful price is inferred from the identified cause.
