---
id: 002-isolate-pair-state-and-recovery
unit: 002-paired-price-execution
intent: 026-jev-price-comparison
status: in-progress
priority: must
created: "2026-09-26T16:33:08Z"
assigned_bolt: 086-paired-price-execution
implemented: false
---

# US-210: Isolate pair state and recovery

## User story

As a user, I want to keep experimental checks from corrupting normal savings or sessions, so the price comparison is trustworthy and actionable.

## Assigned requirement

FR-7; shared NFRs in ../../../requirements.md. The complete pair contract is in
../../../experiment-design.md.

## Acceptance criteria

- [ ] Given existing side-effectful coordinator/search-job code, when pairing is introduced, then per-method execution/validation is separated from canonical recording; baseline alone applies canonical effects once.
- [ ] Given a successful candidate with failed baseline, when finalizing, then its validated result is reported/stored as experimental without replacing baseline history, failure counts, qualification or savings.
- [ ] Given either arm returns session refresh/reauth/key failure hints, when processing, then candidate effects are discarded and baseline verified refresh obeys revision checks after starting snapshots are frozen.
- [ ] Given crash/restart between arms or after unknown provider completion, when recovery runs, then preserve completed siblings, finalize interrupted/unknown outcomes and do not blindly rerun billed work.
- [ ] Given user purge/revocation/disconnect racing with execution or delivery, when authority is rechecked, then access restrictions win and candidate work cannot recreate removed state.

## Technical notes

Persist before remote work. Use compare-and-set/idempotent receipt or equivalent tested transaction boundary.

## Dependencies

Requires: US-209.
Assigned bolt: 086-paired-price-execution. Downstream dependencies are recorded in units.md and bolt frontmatter.

## Edge cases

Missing/ambiguous evidence is an explicit terminal, never guessed success. Interrupted or denied work
retains cost and method attribution. Recheck user/session authority at execution and delivery.

## Out of scope

Inventory conversion, Stagehand removal, autonomous booking actions, provider/payer fallback and
claims of qualification without evidence.
