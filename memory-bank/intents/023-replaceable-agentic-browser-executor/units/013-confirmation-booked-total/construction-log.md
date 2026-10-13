---
unit: 013-confirmation-booked-total
intent: 023-replaceable-agentic-browser-executor
created: 2026-10-10T02:00:18Z
last_updated: 2026-10-12T22:26:23Z
---

# Construction Log: Confirmation Booked Total

## Original Plan

**From Inception**: 1 bolt planned
**Planned Date**: 2026-10-10T01:59:26Z

| Bolt ID | Stories | Type |
|---------|---------|------|
| 092-confirmation-booked-total | US-226, US-227, US-228 | ddd-construction-bolt |

## Replanning History

| Date | Action | Change | Reason | Approved |
|------|--------|--------|--------|----------|

## Execution History

- **2026-10-10T02:00:18Z**: 092-confirmation-booked-total started - Stage 1: domain-model. The owner selected
  this work directly and waived per-stage approval for this task while requiring every stage to
  be recorded; each stage checkpoint below is therefore recorded as waived, not approved.
  Relevant prior decisions loaded from the index: ADR-027 (account inventory is authoritative),
  ADR-028 and ADR-039 (positive-only reconciliation), ADR-048 (grouped confirmation facts) and
  ADR-049 (trusted current-list reconciliation).
- Stage constraint note: the domain-model and technical-design stages forbid reading source. The
  source had already been read during the diagnosis that preceded inception; no source file was
  opened during those two stages, and the earlier out-of-process draft stayed outside the worktree.
- **2026-10-10T02:00:33Z**: 092-confirmation-booked-total stage-complete - domain-model → technical-design.
  Checkpoint waived by the owner for this task. The model covers all three stories.
- **2026-10-10T02:01:25Z**: 092-confirmation-booked-total stage-complete - technical-design → adr-analysis.
  Checkpoint waived by the owner for this task. No source file was read during the stage.
- **2026-10-10T02:01:25Z**: 092-confirmation-booked-total stage-complete - adr-analysis → implement. One
  ADR-worthy decision was identified and recorded: ADR-058 (page-verified total replaces a saved
  total), a deliberate narrowing of the saved-fact authority in ADR-039/048. The decision index
  now lists 56 decisions. Checkpoint waived by the owner for this task.
- **2026-10-10T02:04:30Z**: 092-confirmation-booked-total stage-complete - implement → test. The set-aside
  draft was re-applied and checked against the recorded design, then extended with the
  content-free reason codes and coverage-diagnostic counters the design requires. Source touched:
  confirmation facts reader, grouped reader, runtime adapter, the two observation types, the
  observation merge and the SQLite conflict and merge rules. No schema, config or dependency
  change. Checkpoint waived by the owner for this task.
- **2026-10-10T02:05:01Z**: 092-confirmation-booked-total test stage in progress, not complete. Automated gate:
  3,125 passed, 1 skipped; Ruff and mypy (131 modules) clean; 16 validator tests passed; artifact
  validation 0 errors and 0 inconsistencies. US-228's affected-caller replay has not been run and
  needs separate owner approval because it uses the production host and the caller's saved
  session. The completion cascade was not run; Bolt092, US226–228 and Unit013 remain in progress.
  Nothing is committed, pushed, merged or deployed.
- **2026-10-10T02:07:12Z**: Added the missing US-227 assertion that a stale savings opportunity is removed on
  replacement and kept on a rejected unverified change. Final-source gate rerun: 3,125 passed,
  1 skipped; Ruff and mypy clean. Test stage still in progress pending the affected-caller replay.
- **2026-10-10T02:12:09Z**: The owner approved the affected-caller replay and set the order: let the meal-plan
  work finish first, then replay against the real confirmation page, and only then commit and
  push. Observed state: PR #77 (`claude/meal-plan-equivalence`) is open and a `mealplan-20261010`
  release kit already exists on the production host, so that release is in flight. Production
  still runs the image started 2026-10-04T03:24:11Z. No replay was started and the host was not
  touched beyond read-only inspection. A background watcher waits for PR #77 to be merged and
  its image to be live and healthy with no staging containers. Next steps then: rebase onto
  main, rerun the gates, replay with `scripts/inventory_refresh_probe.py` on cloned state with
  the daemon paused, and record the result here.
- **2026-10-10T02:22:43Z**: Registry collision found. A peer session reported, and both PR heads confirm, that
  open PR #77 (meal plan) and PR #78 (Jev price method) each claim story IDs from US-216 and
  schema v20, and #78 claims bolt 089 and ADR-056. This uncommitted bolt claims the same bolt
  number, US-216–218 and ADR-056. It makes no schema change, so the schema-version conflict does
  not involve it. Decision: this work lands last; after #77 and #78 are merged it is rebased and
  renumbered to the next free bolt, story and ADR numbers, and every reference in these records
  is updated then. The numbers written above are provisional until that rebase. Both peers were
  told; no peer worktree, PR or release kit was touched. The watcher now waits for #77 merged and
  live in production, #78 merged or closed, and no staging container running.
- **2026-10-10T02:22:56Z**: The session that owns PR #77 confirmed the order (#78, then #77, then this work) and
  the numbers it and #78 will hold: schema v20 and v21, bolts 089–091, US-216–225, ADR-056–057.
  This work is expected to become bolt 092, US-226–228 and ADR-058, to be verified against main
  at rebase rather than assumed. That session asked that the daemon not be paused until it
  reports #77 promoted, healthy and its own read-back refresh finished; agreed, and consistent
  with the owner's instruction to let that work finish first.
- **2026-10-10T03:29:49Z**: Verified after a peer report: PR #78 merged as 9115324 and production runs
  `booksaver-agent:jevprimary-7b18adc` since 2026-10-10T02:42:11Z, healthy, schema v20. PR #77
  is still open, now conflicting with main, and the session that owned it has ended; its
  `mealplan-aa7be3b` image predates the new base. The owner's condition for the replay ("let the
  meal-plan agent finish first") therefore cannot be met until someone resumes that work. No
  replay, rebase, renumbering or commit was done; the decision on whether to keep waiting or go
  ahead of #77 was returned to the owner.
- **2026-10-12T21:55:29Z**: Rebased and renumbered. PR #78 (9115324) and PR #77 (063c3e4) are merged and
  released; production has run `booksaver-agent:mealplan-d19f7b5` since 2026-10-10T08:14:56Z,
  healthy, with release evidence merged as #81 and no open pull request. The owner had chosen to
  go ahead of #77 while it was stalled; it landed first anyway, so the original order holds.
  The uncommitted work was moved onto main 108bc23. Five files conflicted with the meal-plan
  change and were resolved by keeping both sides: the two observation types, the confirmation
  facts reader and its tests, and the decision index. This bolt is now 092, its stories
  US-226–228 and its decision ADR-058; 089, US-216–219 and ADR-056 belong to the Jev price
  method and 090–091, US-220–225 and ADR-057 to meal plan. Identifiers in the entries above the
  collision entry were rewritten to the new numbers; the two collision entries keep the numbers
  as they were claimed at the time. Unit013 and FR34–36 are intent-local and unchanged.
- **2026-10-12T21:57:00Z** (minute precision): Post-rebase gate on main 108bc23 plus this work:
  3,259 passed, 1 skipped; Ruff clean; mypy clean for 133 modules; artifact validation 0 errors,
  0 inconsistencies.
- **2026-10-12T21:59:50Z**: Candidate image `booksaver-agent:bookedtotal-wip-9a45af6` built on the
  production host from the uncommitted source on base `mealplan-d19f7b5`, kit
  `/opt/booksaver-releases/bookedtotal-20261012`. Offline smoke passed (installed source carries
  the change). The tag is a work-in-progress replay candidate, not a release image.
- **2026-10-12T22:00:57Z**: Replay attempt 1 failed before any Booking.com request: the probe
  could not import the image's `scripts` package. Production was paused from 22:00:20Z to
  22:00:57Z and restored healthy on its original image. My wait loop also matched its own
  command line and ran to its limit; no effect on the host.
- **2026-10-12T22:09:54Z**: Replay attempt 2 on the affected caller's real confirmation page
  (cloned state, data volume read-only, notifications disabled, production paused 22:08:22Z to
  22:09:54Z and restored healthy). Result: refresh complete, 1 discovered, 1 eligible. The refund
  schedule sentence was read and the refund deadline 2026-11-21 recorded. The booked total stayed
  USD301: the new diagnostic reported `booked_total:final_price_statement`. US-228 not met.
- **2026-10-12T22:11:50Z**: Replay attempt 3 added a one-off capture of the lines around the
  "Price" heading of the owner's own page, written only to the root-only kit log (production
  paused 22:10:23Z to 22:11:50Z, restored healthy). Observed layout: the refund schedule label on
  its own line; `1 room US$309`; `12 % TAX US$37.08`; `Price`; `(for 2 guests)`; `US$346.08`;
  then the heading `Additional Info` directly, with no final-price statement. Amounts carry the
  `US$` prefix; no bare dollar sign appears.
- **2026-10-12T22:12:52Z**: Design amended from that evidence before changing code (see the technical design's
  amendment): accept a price block closed by `Additional Info` when no final-price statement is
  rendered and a reconciled VAT/TAX row proves the total tax-inclusive; drop the unobserved bare
  dollar sign so only prefixed or coded currencies are read. The capture is removed from the
  probe before the qualifying replay.
- **2026-10-12T22:14:30Z** (minute precision): Reader corrected per the amended design and the
  dollar tests rewritten to the observed layout. Gate: 3,257 passed, 1 skipped; Ruff and mypy
  (133 modules) clean.
- **2026-10-12T22:17:07Z**: Replay attempt 4, image `bookedtotal-wip-0478f4c`, capture removed
  (production paused 22:15:36Z to 22:17:07Z, restored healthy on its original image). Refresh
  complete, 1 discovered, 1 eligible, no unknown facts. Saved USD301 became USD346.08 on the
  reservation and the same monitoring booking with history kept; refund deadline 2026-11-21;
  other callers' rows identical before and after; the production row itself still reads USD301
  because every write went to the discarded clone. US-228 acceptance met.
- **2026-10-12T22:18:02Z**: Test stage evidence recorded in the test report, story criteria amended for
  the two layout facts, ADR-058 qualification appended. Test-stage checkpoint waived by the owner
  for this task, as for the earlier stages.
- **2026-10-12T22:18:16Z**: 092-confirmation-booked-total completed - All 5 stages done. Ran
  `node .specsmd/aidlc/scripts/bolt-complete.cjs 092-confirmation-booked-total --last-stage test`:
  bolt in-progress → complete, US-226–228 complete and implemented, Unit013 complete; Intent023
  unchanged with two other incomplete units. Story index and unit list aligned. Nothing is
  committed, pushed, merged or deployed; the production booking still reads USD301 until release.
- **2026-10-12T22:26:23Z**: Operations handoff. Committed as baf9b29, PR #82; Bugbot merge gate passed on that
  head; merged as 8a3eb1e. Exact image `bookedtotal-baf9b29` passed Development and both Staging
  checks (offline snapshot; live affected-caller replay 22:21:42Z–22:23:26Z, USD301 to USD346.08)
  and was promoted at 2026-10-12T22:25:30Z with backup and rollback tag; production health,
  integrity and public health verified. The production reservation is corrected by the first
  synchronization after promotion, which has not happened yet. See release
  `baf9b29-confirmation-booked-total`.
