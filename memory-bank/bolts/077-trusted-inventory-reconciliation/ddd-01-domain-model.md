---
stage: model
bolt: 077-trusted-inventory-reconciliation
created: 2026-09-19T22:04:01Z
---

# Domain model

## Entities and aggregate

- Reservation: caller-owned confirmation identity, observed lifecycle/facts and historical state.
  Cancellation, rebooking and absence retirement are distinct transitions. A new confirmation is
  distinct even if property/dates match; unknown identity never authorizes a transition.
- Inventory run: caller, session revision, run identity, recognized current-list scope and observations.
  Its reconciliation transaction is the aggregate boundary; other callers and out-of-scope rows remain unchanged.
- Monitoring projection: derived only from eligible positively verified reservation facts and the
  existing current-run receipt; retired/current/cancelled/incomplete records cannot acquire authority.

## Value objects

- ActiveInventoryCoverage: code-owned proof of positively qualified root exhaustion, exact resolved
  group/card membership, no unresolved/conflicting/truncated source and stable pre/post membership.
  Bind it to caller, run, session revision and UPCOMING/CURRENT scope, with final auth/safety checks.
- Observation identity: exact caller + confirmation, not hotel/date similarity.
- Verification state: positively seen this run, preserved but unverified, or retired by proven absence.

## Services and repository contract

Coverage validation rejects unsupported/forged/stale/wrong-scope proof. Reconciliation validates
positives, applies explicit lifecycle evidence and retires only absent covered active identities in
one caller-scoped transaction. Repository preserves reservation/history rows and updates projections;
any conflict rolls back the whole reconciliation. Presentation distinguishes verified current facts
from saved unverified history and never calls an absence-only retirement a cancellation.

## Events and vocabulary

InventoryScopeVerified permits covered reconciliation. ReservationRetiredFromCurrentList records
absence retirement without a remote mutation. ReservationCancellationObserved records exact positive
cancellation evidence. InventoryIncomplete retains positives and saved unseen rows without authority.
“Complete” means a validated covered scope, not a claim about every historical/account service item.
