---
stage: test
bolt: 077-trusted-inventory-reconciliation
created: 2026-09-19T23:03:43Z
status: complete
---

# Reconciliation verification

## Earlier automated evidence

- Full source suite: **2,690 passed**, 52 existing warnings, 51.19 seconds.
- An additional root-membership-churn regression was added during that run; the final reader
  selection separately passed **66 tests**. Do not sum overlapping selections.
- Ruff clean; mypy clean for 122 source modules; 16 AI-DLC validator tests passed.
- Artifact/status validation has zero errors/inconsistencies; historical warnings remain.
- Actual Chromium DOM tests validate selected-tab binding, explicit accessible count/positions,
  missing/duplicate positions, pending controls, busy state, explicit empty scope, and structural
  cancellation headings. These fixtures are synthetic, not captured Booking.com acceptance.
- Domain/persistence tests cover caller/execution/lease binding, model-only rejection, exact
  cancellation and replacement identity, scoped absence, preserved history/other callers,
  projection/savings retirement, rollback on conflicts and later positive reappearance.
- Telegram tests label saved unseen rows unverified and exclude retired rows from the active list.
- Review found and corrected root-count substitution by outside-panel links and case-sensitive
  cancellation conflicts. A post-passive-read safety check preserves terminal behavior.
- One existing canary test used fixed August data with the real current clock. Its test clock is
  now fixed within that fixture's active review window; production qualification code is unchanged.

## Fresh-caller qualification history

Fresh authentication is valid September20 through September24. The initial notification-free cloned
replay returned partial with **4 positives**, **2 eligible**, **0 unresolved**, and two trip groups
with four items each. The EUR104 old reservation and EUR94 replacement both remained active.
The actual root did not provide the generic accessible-list evidence; full absence authority was
correctly withheld, but the user's intended reconciliation was not achieved.

The observed root embeds a qualified Apollo page-cache namespace with exact CURRENT/UPCOMING query
scope, explicit first-page null token, rowsPerPage10, terminal null next token/backfill, two unique
Trip references and four non-cancelled items per trip. The code-owned parser/collector binds those
references/counts to actual selected Active-panel anchors. Offline Chromium against the captured
DOM, with executable scripts and network disabled, verified a two-trip root proof. **57 focused
parser regressions passed**. The earlier full-suite result above predates this refinement and is
not claimed as the final candidate gate.

Live cloned candidates 2, 3 and 4 also returned four positives/two eligible, two verified groups
and zero unresolved, while correctly withholding completeness. These earlier candidates did not
establish absence authority; later acceptance is recorded separately below.

## Final-root evidence failure and refinement

Captured initial root evidence included full selected Active role/aria bindings. After browser
history return, the same cards/cache remained but role/aria-selected/aria-controls were removed
from tab buttons and tablist. This explains the final-proof rejection; those positive counts did
not authorize retirement. The implementation retains the original proof standard and adds only
short guarded passive settling followed by at most one metered code-owned GET re-navigation to
the exact fresh qualified current root, same tab. It must reacquire full selected Active/cache
proof and unchanged membership/count, with normal auth/safety/deadline checks. No tabindex shortcut,
Page.reload, form replay, new model action or stale-proof reuse is accepted.

The runtime safety callback and reader refinement were implemented and exercised by later
replays. The exact-image Operations gate remains separate.

## Actual-caller acceptance: live candidate6

At **2026-09-20T17:51Z** (reported to minute precision), the notification-free normal-coordinator
replay on cloned state succeeded. Root raw URLs differed but canonical membership matched and the
trusted scope proof passed. Both trip groups were verified; four detail visits yielded four parsed
reservations, with three completed skips, one known non-hotel and zero unresolved work.

The report was **COMPLETE**, with **4 discovered**, **2 eligible** and no failure. The old EUR104
reservation became **ABSENT**, ineligible and attributed to this run. The separate EUR94 replacement
remained **UPCOMING**, eligible and attributed to this run. This is accepted affected-caller
reconciliation on the clone; production was untouched.

A final same-page root guard and corresponding empty-case guard were added after live6. The prior
full run passed **2,800 tests**, and the focused reader selection passed **77 tests**. The pre-review
release-quality suite including those three regressions passed **2,803 tests**, with **52 existing
warnings**, in **51.16 seconds**. Ruff and mypy (**123 source modules**) passed. That historical suite log
is `/tmp/booksaver-reconciliation-release-quality.log`. These overlapping selections are not summed.

Canonical equality uses the existing InventoryTraversal._key only: exact qualified trip path and
trip_id, ignoring existing aid/label/sid presentation parameters and query ordering. Equal lengths
and unique canonical sets reject duplicates; changed trip identity still blocks proof.

Construction acceptance is complete for US192–194: deterministic authority/isolation/persistence/
Telegram regressions and actual-caller clone reconciliation passed. Exact installed-image staging
must still qualify the latest source, including guards added after live6.

## Operations handoff limits

Final-head Bugbot, exact installed-image Development/Staging, merge, backup/rollback, promotion
and production verification remain pending. Exact-image staging must qualify the latest root/
empty-case guards as well as the reconciliation assertions. Native Telegram interaction is not
claimed by cloned coordinator evidence.

## Post-review qualification follow-up

Bugbot identified two medium issues, both corrected before promotion:

- Enforce exactly **rowsPerPage10**, matching the accepted exhaustion contract, instead of accepting
  arbitrary values from 1 through 25.
- Collect only bounded Trip records referenced by the selected Active query, rather than all cache
  Trip keys. Unreferenced historical records (fixtures with 30 and 150) do not block the otherwise
  qualified Active scope. Extra or mismatched Active membership still fails the proof.

Focused verification passed **69 parser tests** and **170 total targeted parser/DOM-reader tests**;
these overlapping selections are not summed. The new full suite passed **2,818 tests**, **52 existing warnings**, in **52.42 seconds**;
Ruff and mypy (**123 modules**) are clean. The log is
`/tmp/booksaver-reconciliation-post-review-quality.log`; the earlier 2803-test result belongs to the
previous candidate. Exact installed image fe8ba21 passed Development/Staging but was not promoted
and is superseded by these source fixes. The replacement image needs fresh exact-source checks,
Development/Staging and current-head successful Bugbot before merge/promotion.

Bolt077's official construction completion remains recorded. This is qualification follow-up;
no second cascade, current-candidate live pass or production completion is claimed.

## Reviewed replacement image qualification

Source 153d4320dd553e2d2c58d5231949697991009212 produced exact image `sha256:cddc642f8a3e6b1babaa070000c530027362de2933ab47575008fc7d5141155b`.
All 123 installed modules, eight pins/`pip check`/CLI passed; Development passed in 2.72 seconds.
Exact installed-image Staging passed 39 checks / 0 failures: COMPLETE / 4 discovered / 2 eligible, old absent/archived,
separate replacement upcoming/active/eligible, 658 other-caller rows unchanged, integrity/FK violations 0 and
read-only original source digest unchanged. Current-head Bugbot SUCCESS in 3m29s and merge gate passed
(two resolved threads, zero unresolved). This replaces fe8ba21 qualification for release purposes.

PR53 merge is requested but unconfirmed after GitHub 504/REST 405 “Merging already in progress”;
latest read is OPEN/merged=false. No merged or production result is claimed. Record actual
promotion and normal production acceptance separately after confirmed merge.

## Production acceptance recorded

PR53 merged at 2026-09-20T18:12:16Z as ef51bc8a5b4367d55e59af4644d1d3178db7d957, full tree
identical to reviewed 153d432. The exact qualified cddc642 image was promoted and independent
production verification passed at 2026-09-20T18:15:28Z. Normal caller refresh passed 38 assertions,
COMPLETE / 4 discovered / 2 eligible, old EUR104 ABSENT/ineligible/archived with identity/total preserved, distinct EUR94 active/
eligible, 658 other-caller rows unchanged and SQLite/FKs clean. No notifications were sent. Service,
health, backup/rollback and monitoring evidence is in Unit012 deployment/history.md. Operations
complete; native Telegram UI remains user-driven and is not claimed as tested.
