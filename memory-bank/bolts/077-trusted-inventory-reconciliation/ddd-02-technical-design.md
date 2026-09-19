---
stage: design
bolt: 077-trusted-inventory-reconciliation
created: 2026-09-19T22:04:01Z
status: accepted
---

# Technical design — accepted contract

Keep the existing single coordinator, browser host/lease, read-only guard, phase deadlines and
shared budget ledger. No browser/LLM output owns persistence authority.

1. Trusted reader acquires recognized selected Active scope and positive root exhaustion/count
   evidence, enumerates groups/direct cards, resolves every active identity and proves exact group
   membership. Scope root/group membership must remain stable through a final return/read.
2. A separate code-owned ActiveInventoryCoverage value carries caller/run/session binding and the
   covered lifecycle set. Diagnostic counts and provider terminal enums cannot construct this value.
3. Validator checks proof binding, recognized evidence and final auth/focus/tab/dialog/safety/limit
   state after awaited reads. Any missing or changed evidence downgrades to positive-only incomplete.
4. Reconciliation atomically upserts validated observations and retires absent UPCOMING/CURRENT rows
   only in the proof's caller/scope. Do not infer cancellation or touch CANCELLED/COMPLETED/UNKNOWN
   history by absence. A conflicting positive fails the transaction, never partial retirement.
5. Explicit positive cancellation requires exact confirmation identity and preserves prior financial
   facts. A replacement confirmation is a separate row; similar hotel/dates cannot merge them.
6. Presentation distinguishes current-run positives, saved unverified unseen rows and retired history.
   Existing current-run price receipts, equivalence, all-in/refundability and occupancy gates remain.

## Qualified acquisition and explicit cancellation contract

Require a selected Active tab bound through aria-controls to its actual panel, plus an explicit
accessible list total with aria-setsize/aria-posinset covering every trip item and bound to the exact qualified anchors inside that list. Counts
from outside-panel links cannot substitute membership. Reject busy/progress
or pending pagination controls, missing/duplicate positions, root direct/unknown work and truncation.
Compare pre/post root membership and total; require exact group counts and stable pre/post group
membership. No unresolved work may survive. Final authentication/focus/safety and limits remain
necessary after awaited acquisition. The model schema cannot populate the proof.

This is a generic positive DOM contract, not a claim that current Booking.com markup satisfies it.
Actual page qualification is mandatory. An unsupported live root remains incomplete even if all
visible groups were visited. The affected father's session is currently expired; refreshed login
and real rendered root evidence are pending, while implementation remains authorized.

Explicit cancellation requires a unique numeric confirmation and the exact recognized heading
“Your booking/stay/reservation is/has been cancelled/canceled”, without contradictory status.
The status must also be a unique rendered heading; contradictory statuses are checked
case-insensitively. The evidence is code-bound to the observed detail identity; a cancelled card alone is insufficient.
Use existing transaction/projection boundaries and keep saved financial/history facts intact.

## Verification and release

US194 covers reader-to-persistence/presentation tests, actual-caller qualification and quality gates.
Adversarial fixtures must reject spoofed completeness, root/group churn, direct-root omissions,
unknown/duplicate/conflicting identities and final auth/safety failures. Record proof/retirement
counts without raw source text, authentication URLs or identifiers. Use the existing protected
isolated replay; no production mutation during diagnostic qualification. Operations gates remain
separate from construction completion and unchanged in strength.
