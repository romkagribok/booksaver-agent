---
stage: model
bolt: 074-grouped-trip-discovery
created: 2026-09-13T16:11:46Z
---

# Domain Model: Grouped Trip Discovery

## Entities and aggregate boundaries

The caller owns the authenticated session, inventory run, saved reservations, and monitoring
projection. A trip group is a presentation container that may hold several reservations or mixed
product types; it is not itself a hotel reservation identity. A hotel reservation has its own
identity, lifecycle evidence, stay dates, room/occupancy facts, total/currency, and refundability.
A reservation detail visit supplies evidence for that reservation only.

The inventory-run aggregate contains positively observed records and a bounded coverage worklist.
Worklist entries represent code-observed trip groups, reservation targets, and required detail
views. Observation, visitation, accepted facts, rejection, explicit non-hotel skip, and unresolved
work are different states. Completing the worklist is a coverage outcome, not authoritative account
completeness. Agentic reconciliation stays INCOMPLETE/positive-only and never deletes unseen rows.

## Lifecycle and eligibility invariants

A first-time identity must be able to carry explicitly observed lifecycle facts through the same
validation/reconciliation path as a saved match. Saved data is not a source of stronger truth merely
because it already exists. Future dates alone do not establish uncancelled/upcoming lifecycle;
cancelled/unknown/conflicting state cannot be guessed away. Likewise, acceptance of a reservation
identity does not prove that all required monitoring facts are available.

Current versus upcoming is a user-facing stay-date distinction evaluated by existing date policy.
An active group label cannot make all of its children upcoming or price-eligible. Hotel-only,
explicit refundability, same property/stay/room/occupancy, and currency-aligned all-in total rules
remain unchanged. Missing or invalid required facts preserve the reservation but fail eligibility.

## Services and repositories

The existing Browser Use host owns one bounded episode and maintains the worklist from guarded
observations. Its action/destination guard, caller-bound session, runtime limits, and coordinator
lease remain authoritative. Validation accepts typed facts, rejects invalid/conflicting evidence,
and creates current-run positive receipts only when permitted. Reconciliation persists accepted
records and derives monitoring eligibility. Telegram renders persisted caller outcomes; it does
not decide lifecycle or eligibility.

Existing caller-scoped repositories remain the storage boundary. Diagnostic coverage contains
bounded code-owned counters/reasons, not page text, URLs, reservation identifiers, credentials,
cookies, or model reasoning. No new destructive repository operation is introduced.

## Events and vocabulary

- Group/target observed: guarded page evidence adds reachable work, subject to a hard bound.
- Target visited: an allowed navigation and post-action check reaches that work item.
- Detail accepted/rejected: existing validation handles reservation-specific facts.
- Non-hotel skipped: positive product-type evidence excludes an out-of-scope item; unknown type
  remains unresolved rather than silently skipped or treated as a hotel.
- Coverage settled/partial: all observed in-scope work accounted for, or an explicit remaining gap.
  Neither event authorizes absence reconciliation or silently grants monitoring eligibility.
- Inventory accepted: validated positive evidence exists; it is not full-coverage or price success.

## Checkpoint and uncertainty

The user authorized this narrow end-to-end correction and its verification loop. This model covers
US-187 through US-189 without changing transaction, equivalence, refundability, or absence authority.
The concrete grouped-page navigation shape and live coverage expectations still require fresh login
and current caller evidence; those unknowns do not prevent the confirmed lifecycle correction.

## 2026-09-13T16:13:05Z - Partial saved records must remain detail work

A saved identity is not necessarily a complete reservation. Production evidence shows partial new
rows with name, dates, and room but missing property reference, booked total, occupancy, and
refundability. Reusing those rows as already-processed semantic matches causes retry to skip the
very details needed for eligibility. A previously saved partial record must therefore remain
unresolved detail work on a later run until its required facts are positively observed and validated.

Only already-eligible complete saved records may qualify for the existing processed-match shortcut;
all caller-owned confirmation hints remain available for identity matching. Hints alone never
complete work, supply missing facts, or grant a current-run receipt. A complete saved record still
requires current-run positive observation before monitoring. This preserves the owner's qualified
path while allowing retry of incomplete records to make progress.
