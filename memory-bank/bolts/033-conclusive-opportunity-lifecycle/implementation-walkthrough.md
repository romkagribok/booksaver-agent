---
stage: implement
bolt: 033-conclusive-opportunity-lifecycle
created: 2026-07-27T02:39:16Z
updated: 2026-07-27T02:46:10Z
---

# Implementation Walkthrough: Conclusive Opportunity Lifecycle

## Summary

Current rebook actionability now follows the latest conclusive check linked to each opportunity.
Technical failures preserve the last verified saving, while later successful or no-equivalent
market observations replace or invalidate it without modifying history.

## Structure Overview

One reusable SQLite common-table expression derives current opportunities from check history,
savings history, booking activity, and ownership. The repository uses it for both current read
operations and the immediate transaction that creates a guided rebook session. Application and
Telegram layers continue to consume the repository contract and now use accurate generic
currentness guidance.

## Completed Work

- [x] `src/booksaver/infrastructure/persistence/sqlite_store.py` - Derives current actionability from
      latest conclusive checks and reuses the rule in the atomic session guard.
- [x] `src/booksaver/application/rebook_service.py` - Reports conclusive currentness failures without
      assuming a newer lower price exists.
- [x] `src/booksaver/infrastructure/telegram/rebook_gate.py` - Gives accurate refresh guidance for
      replaced and invalidated selections, shows the last successful verification time, and avoids
      optimistic picker edits before atomic session creation.
- [x] `tests/integration/test_savings_repo.py` - Covers technical preservation, conclusive
      invalidation, smaller-saving replacement, restoration, equal timestamps, history, and
      history-before-opportunity behavior.
- [x] `tests/integration/test_rebook_repos.py` - Covers atomic acceptance after technical failure and
      rejection after conclusive invalidation.
- [x] `tests/integration/test_user_scoping.py` - Keeps current lifecycle coverage linked to owned
      persisted checks.
- [x] `tests/unit/telegram/test_rebook_gate.py` - Covers picker preservation and generic rejection
      after conclusive invalidation.

## Key Decisions

- **Derive rather than mutate**: Append-only history remains authoritative and no schema migration is
  required.
- **Narrow conclusive classification**: Successful checks and `NO_EQUIVALENT_OFFER` supersede;
  every other failure preserves the prior conclusive state.
- **Order by check time plus insertion ID**: Equal timestamps are deterministic without allowing a
  delayed older check to become current.
- **Fail closed during the two-write success gap**: Once a newer successful check exists, the old
  quote is hidden until its new savings row is persisted.
- **Reuse one query shape**: Listing, lookup, and transaction-time validation cannot drift.
- **Expose evidence age**: Telegram labels choices with their original successful verification time
  and explains that technical failures do not update it.
- **Avoid optimistic callback state**: The acknowledged picker remains unchanged; a separate reply
  says currentness is being checked, and only the confirmation prompt implies atomic acceptance.

## Deviations from Plan

None.

## Dependencies Added

None.

## Developer Notes

An opportunity without a matching source check remains visible to historical diagnostics but is not
actionable. A technical failure after conclusive invalidation does not revive older savings.
