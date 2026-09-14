---
unit: 011-grouped-trip-discovery
intent: 023-replaceable-agentic-browser-executor
status: complete
default_bolt_type: ddd-construction-bolt
created: "2026-09-13T16:10:04Z"
---

# Grouped Trip Discovery

## Assigned requirements

FR-28 / US-187: Traverse grouped trips, their reservations, and required reservation details;
record bounded code-owned coverage evidence and do not stop merely after the first accepted row.
FR-29 / US-188: Keep incomplete facts ineligible and report current versus upcoming stays honestly.
FR-30 / US-189: Prove coverage with deterministic fixtures and the actual affected caller, then
qualify the final reviewed image through staging, promotion, and production verification.

## Context and evidence boundary

The September 8 Unit 010 / Bolt 073 correction accepted partial positives and explicit empty
upcoming views. Its completion and positive replay counts remain valid historical evidence, but
neither established traversal of every grouped reservation and its details for the father.
The September 13 request authorizes closing that remaining gap. Reviewer inspection now confirms a separate first-time lifecycle defect: new identities retain
unknown lifecycle while the saved-match path supplies upcoming; optional submitted facts cannot
repair that field. Valid future reservations can therefore be accepted yet persist as UNKNOWN,
become not_upcoming, and disappear from the upcoming view. Recent father runs accepted one or two
records but still showed zero eligibility. Final design must address this end-to-end projection
path along with evidence-grounded grouped traversal, not merely increase accepted counts.

One Browser Use inventory episode must distinguish trip groups, reservation identities, and
reservation-detail evidence. Group summaries and accepted row counts cannot stand in for coverage.
Authentication, disclosure, caller/session binding, the coordinator lease, action guards, and the
ADR-048 phase deadlines and shared cost/action limits remain authoritative. No background queue, competing browser,
automated booking action, or destructive absence authority is introduced.

## Acceptance and limitations

- Discover all reachable groups/reservations/details in the admitted caller scope within existing
  bounds. If a bound or ambiguous page prevents coverage, report the unresolved work honestly.
- Preserve valid current-run positives and prior saved rows. Coverage evidence does not grant
  permission to delete or deactivate unseen rows or relax identity/refundability/price eligibility.
- Explain current versus upcoming inventory and missing detail facts without turning active-trip
  labels into upcoming-monitoring eligibility or making partial discovery look complete.
- Keep diagnostic output bounded and code-owned; raw account page text, identifiers, secrets,
  credentials, cookies, and model reasoning are not new audit output.
- Deterministic group/detail fixtures and the father's own isolated normal-coordinator replay must
  establish coverage, accepted records, rejected/missing facts, and final eligibility independently.
  A successful owner or empty-account run cannot substitute for that acceptance.

## Authorization and construction entry

The user explicitly authorized the end-to-end AI-DLC fix, iterative verification, merge, and
redeployment for the grouped-trip problem. This covers the scoped inception/construction/operations
checkpoints without repeated routine permission. Final-head successful Cursor Bugbot review and
exact-image staging/promotion verification remain mandatory. Material new security or product scope
would require separate discussion.

Bolt 074 construction is complete after actual-caller replay 22 and the final quality gate.
The grouped reader covered both trips with zero unresolved work and six parsed hotel details;
two future stays qualified, and the normal immediate check returned a validated authenticated
mobile EUR price. See the final test report for deliberately ineligible cases and exact evidence.
Final-head review and exact-image Operations qualification/promotion remain pending.

## Story Summary

- Total stories: 5; all Must; US187–191 complete for construction.
- US-187: Discover every grouped reservation and detail.
- US-188: Preserve strict eligibility and distinguish current stays.
- US-189: Qualify grouped discovery for the actual caller and final image.
- US-190: Close grouped-discovery review edge cases.
- US-191: Close the price submission contract.

## 2026-09-13T16:10:42Z - Authenticated acceptance prerequisite

At this checkpoint, all three inspected caller logins were expired; the father's expiry was
approximately 2026-09-12T05:07:00Z (reported to minute precision). Reconnect has been requested through the current user interaction. Planning
and deterministic regression work continue independently. Actual-caller grouped/detail/lifecycle
acceptance must remain pending until authentication is restored and a fresh run proves it; no
prior partial-positive result is promoted to full acceptance.

## 2026-09-13T16:13:05Z - Confirmed partial-record retry loop

Production partial new rows had name/dates/room but lacked property reference, total, occupancy,
and refundability. Known semantic matching still labeled them processed, causing detail to be
skipped on retry. US-187 now requires shortcut candidacy only for already-eligible complete records,
with all caller confirmation hints retained for identity matching; US-189 verifies retry progress
and preservation of the eligible-owner path. Required facts and current-run receipts remain strict.

## Review follow-up

PR51's final review found delayed-card and inactive-only-group edge cases. Bolt075 and US190
returned this unit to construction for those bounded corrections; Bolt074's successful historical
caller evidence is preserved. Bolt075 and US190 completed through the official cascade at
2026-09-14T19:41:31Z after the 2,609-test/83%-coverage gate. Operations remains blocked from
promotion: initial image A failed staging, and the review-corrected replacement still requires
final-head Bugbot and exact-image Dev/Staging verification. No production release has occurred.

## 2026-09-14T20:01:15Z — Return to Construction

Image B repeated the Park Inn price timeout after qualified inventory/AIRINN. Bolt076 repairs
the independently verified terminal vocabulary gap and retains interruption diagnostics; the
live timeout cause and final release qualification remain under investigation.

Bolt076 construction completed after the 2,623-test final gate. New-image caller qualification,
current-head review and production promotion remain pending Operations work.
