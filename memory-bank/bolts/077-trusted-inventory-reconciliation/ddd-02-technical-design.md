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

Bind the selected Active tab through aria-controls to its actual rendered panel. There are two
narrow code-owned ways to establish root exhaustion; neither accepts model claims:

- Accessible list alternative: explicit aria-setsize/aria-posinset covers every trip item and binds
  every qualified anchor inside that list. Missing/duplicate positions or outside-panel links fail.
- Observed page-cache contract: parse bounded data from the qualified embedded Apollo script
  namespace beginning `b-trips-frontend-trip-xp-mfe`. Require the exact `getTrips` input scope
  CURRENT plus UPCOMING, explicit null first-page token, and recognized rowsPerPage 10. The
  `nextPageDataPaginationData` token and backfill must both be explicitly null. Resolve unique Trip
  references and bind their identities and non-cancelled item counts exactly to the selected Active
  panel's rendered anchors. Missing fields, unsupported shapes, extra/missing/duplicate membership,
  nonterminal pagination or mismatched counts cannot authorize absence.

The new `inventory_root_coverage` module and bounded page JavaScript collector read already loaded
page evidence. They make no API requests, execute no embedded script, and give no model access to
proof construction. Qualified cache metadata alone cannot substitute for actual rendered membership.
Reject busy/progress or pending pagination controls, root direct/unknown work and truncation.
Compare pre/post root membership and total; require exact group counts and stable pre/post group
membership. No unresolved work may survive. Final authentication/focus/safety and limits remain
necessary after awaited acquisition. The model schema cannot populate the proof.

Fresh caller authentication is valid from September20 through September24. The initial cloned replay
still returned partial: four positives, two eligible, zero unresolved; two groups each had four
items, but the actual root did not support the accessible-list contract. The stale EUR104 and
replacement EUR94 reservations both remained active. This is a reproduced limitation, not acceptance.
The captured root's qualified page cache had two unique Trip references, exact rendered membership
and four non-cancelled items per trip. Offline Chromium with executable scripts/network disabled
verified the two-trip proof. The second live candidate replay is running; full actual-caller
reconciliation and release success remain unclaimed until its result and final gates are recorded.

Explicit cancellation requires a unique numeric confirmation and the exact recognized heading
“Your booking/stay/reservation is/has been cancelled/canceled”, without contradictory status.
The status must also be a unique rendered heading; contradictory statuses are checked
case-insensitively. The evidence is code-bound to the observed detail identity; a cancelled card alone is insufficient.
Use existing transaction/projection boundaries and keep saved financial/history facts intact.

## Final-root restoration after history navigation

Live candidate replays 2, 3 and 4 each accepted four positive reservations, with two eligible stays,
two verified trip groups and zero unresolved work, but correctly withheld completeness. Captured
initial root evidence had the selected Active tab role and aria-selected/aria-controls bindings.
History navigation restored the same cards and page cache but stripped those roles and selection/
control attributes from the tab buttons and tablist. Matching cards/cache alone cannot replace the
required selected-scope evidence; tabindex is not an accepted substitute.

After a short guarded passive settling interval, allow at most one metered, code-owned GET
re-navigation to the exact freshly observed qualified current root in the same tab. The normal
read-only navigation path, action budget, deadline and final authentication/source/focus/safety
checks remain authoritative. Do not use Page.reload or replay a form, create a model action, or
reuse old proof. Independently reacquire the full original selected Active/panel/cache contract
and require identical pre/post root membership and counts, plus all existing group evidence.
If navigation or reacquisition fails or evidence changes, remain incomplete and preserve unseen rows.

The main reader and runtime guard implement this bounded restoration. Qualification of the refined
candidate is pending; the previous positive counts are not absence or release acceptance.

## Verification and release

US194 covers reader-to-persistence/presentation tests, actual-caller qualification and quality gates.
Adversarial fixtures must reject spoofed completeness, root/group churn, direct-root omissions,
unknown/duplicate/conflicting identities and final auth/safety failures. Record proof/retirement
counts without raw source text, authentication URLs or identifiers. Use the existing protected
isolated replay; no production mutation during diagnostic qualification. Operations gates remain
separate from construction completion and unchanged in strength.

## Latest actual-caller qualification

Live candidate6 at 2026-09-20T17:51Z (minute precision) established trusted complete scope and
correct clone reconciliation: four discovered/two eligible, old EUR104 absent/ineligible, distinct
EUR94 replacement upcoming/eligible. Raw root URLs differed while canonical membership remained
equal under the existing InventoryTraversal._key: exact qualified trip path plus trip_id, ignoring
existing aid/label/sid presentation parameters and ordering only. Equal lengths and unique canonical
sets prevent duplicates; a changed trip identity remains rejected. The proof still requires the original selected Active/cache, membership/count and final
safety contract; raw URL presentation differences alone do not change trip identity.

The final same-page root and empty-case guards were added after that replay. The final 2,803-test
gate and Ruff/mypy123 passed. Exact installed-image qualification is still required; no staged,
merged or deployed result is inferred.
