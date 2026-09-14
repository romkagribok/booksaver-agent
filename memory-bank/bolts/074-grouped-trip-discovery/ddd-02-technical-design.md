---
stage: design
bolt: 074-grouped-trip-discovery
created: 2026-09-13T16:12:37Z
---

# Technical Design: Grouped Trip Discovery

## Confirmed lifecycle correction

Reviewer evidence identifies the first-time identity path retaining unknown lifecycle while saved
matches supply upcoming; optional detail facts cannot currently supply lifecycle. Add an optional
explicit lifecycle fact using the existing domain vocabulary and instruct the agent to submit the
lifecycle it actually observes. Keep absence of evidence unknown. Future dates cannot manufacture
uncancelled/upcoming status, and cancelled/conflicting facts must never be overwritten through
inference or cached-row convenience.

Route the fact through the existing guarded submission helper, inventory validator, reconciliation,
and caller-owned persisted projection. Validation remains authoritative for allowed values,
current-run identity binding, and conflicts. No unconditional eligibility override is introduced.
A dedicated regression file exercises helper → validator → reconciliation → persisted display and
eligibility for first-time versus saved-match records. Include explicitly upcoming with valid future
facts, current stays, cancelled, missing/unknown lifecycle, and contradictory evidence. A valid
first-time upcoming hotel with complete qualifying facts must be visible and eligible under the
same rules as an equivalent saved match; accepted counts alone cannot satisfy the regression.

## Bounded grouped-trip worklist

Keep one existing Browser Use host/episode under its current session lease, coordinator admission,
and code action/destination guards. The host maintains a bounded, deduplicated worklist for
code-observed trip groups, child reservation targets, and required detail views. Targets originate
from the actual allowed page representation; arbitrary model URLs or reported counts cannot add
trusted coverage or authorize navigation.

Each observed target records only the state needed to continue traversal and account for outcome:
unvisited, visited with detail work remaining, validated hotel observation, explicit non-hotel skip,
or unresolved/rejected with a closed reason. Detect loops/duplicates without endless revisits.
After a positive reservation submission, continue within residual time/action/cost limits while
observed relevant work remains. A completion request cannot silently discard that work; the host
records the unresolved remainder or directs bounded continuation through the same guarded episode.
Do not allocate a second browser, new top-level budget, unbounded retry, or same-job adapter fallback.

Mixed trip contents require a positive non-hotel type before skipping an item. Unknown type,
inaccessible detail, ambiguous group expansion, contradictory cardinality, or incomplete pagination
remains unresolved. Actual rendered structure and guards determine accessible scope; no fixed group
count or guessed link/selector is authorized by this design.

## Retry must collect missing facts from partial saved records

Production partial rows contain name/dates/room but lack property reference, booked total,
occupancy, and refundability. Coordinator known-match selection currently admits these minimal
identities, while the prompt treats a matched card as processed and skips detail. This creates a
repeatable incomplete-record loop rather than a transient model failure.

Restrict the processed semantic-match shortcut to saved records already eligible under the full
existing fact rules. Retain all caller-owned confirmation hints for identity recognition, including
ineligible/partial rows, but do not let those hints suppress required detail work. Prompt/worklist
handling must preserve an unresolved detail task for every partial saved reservation. On retry,
newly observed facts still pass the normal identity/lifecycle/refundability/currency validation and
current-run receipt boundary; stored data never gains new authority.

Main owns this coordinator/prompt integration. Add regressions proving that partially saved records
are excluded from the processed shortcut and require details on retry, while already-eligible owner
records retain the existing shortcut. Trace a partial saved record receiving complete valid current
facts through reconciliation and eligibility; accepted identity counts alone do not prove progress.

## Coverage and persistence contract

Coverage audit is separate from `InventoryCompleteness.INCOMPLETE`. Even when all observed reachable
work is settled, agentic inventory remains positive-only and cannot mark an unseen saved row absent,
delete it, or deactivate monitoring through inferred absence. Partial traversal may preserve accepted
positives, but every monitoring receipt still requires that reservation's valid current-run facts.

Use bounded code-owned coverage counters and allowlisted terminal reasons in the existing run/audit
boundary where feasible. Do not persist raw page text, URLs, confirmation numbers, cookies, credentials,
or model reasoning as new diagnostic evidence. Runtime worklist targets are ephemeral. No database
migration is assumed; any necessary persistence-contract addition must be documented and tested
before adoption. Explicitly distinguish observed targets, visited targets, accepted hotel records,
known non-hotel skips, and unresolved detail work in qualification evidence.

## Current and upcoming presentation

Keep lifecycle validation and date classification out of Telegram formatting. Apply existing stay-date
policy to accepted caller-owned records and label current versus upcoming stays accurately. Preserve
successfully observed records whose required monitoring facts are missing, with a plain ineligibility
reason. Filtering current/date-less records from an upcoming list cannot turn successful observation
into loading failure or an authoritative empty-account claim. Active trip headings are insufficient
to infer reservation lifecycle, cancellation state, or eligibility.

## Guarding, ownership, and verification

All worklist navigation remains inside the existing allowed destinations, action guard, caller session,
current disclosure/routing, and global lease. Recheck runtime safety after awaited browser operations;
authentication loss, cancellation, unsafe action, and time/action/cost limits retain precedence over
buffered positives or coverage state. Keep original safety/equivalence/refundability rules unchanged.

The reviewer owns the optional explicit lifecycle fact/prompt and dedicated pipeline regression file.
The main agent owns grouped worklist implementation, integration, final evidence, and release. Fixture
coverage includes multiple groups/children/details, continuation after first accepted record, mixed
non-hotel and unknown type, missing/contradictory facts, duplicate/loop targets, and guard/limit exits.
Validate the actual father's caller path with fresh authentication, isolated state, production-read-only
source, notification suppression, and serialized browser work; compare discovered coverage and complete
facts against the observed account rather than counting accepted rows only.

Then run repository quality gates, successful final-head Cursor Bugbot, exact-source image checks,
staging, exact-image promotion, and production verification. Record native Telegram and price-result
acceptance separately. Retain protected backups/rollback and verify daemon restoration after probes.

## Assumptions, pending evidence, and ADR analysis

The lifecycle correction is established enough for implementation now. The exact grouped-page
structure, detail navigation transitions, and final worklist extraction representation remain design
assumptions pending refreshed login/current page evidence. Adjust these within the bounded host/guard
contract once observed; record consequential deviations before implementation. All inspected sessions
were expired during planning, so actual-caller coverage/eligibility acceptance remains pending. Keep
the bolt/stories in progress if that live criterion cannot be verified.

Existing ADR-021 serialization, ADR-027/028 inventory authority, ADR-036 trusted control plane,
ADR-039 positive-only reconciliation, and ADR-044/045 inventory routing cover the bounded correction.
No new service/provider, transaction power, absence authority, or relaxed pricing rule is introduced;
no separate ADR is needed for the established contract. Revisit ADR needs if concrete findings require
a new architectural/persistence boundary. The user's end-to-end approval covers the narrow model,
design, implementation, verification, and release checkpoints; this is not a declaration of completion.

## Observed implementation refinement (2026-09-13)

Fresh caller authentication enabled isolated, notifications-disabled live inspection. The account
has two trip groups and accommodation details behind each group. The mobile confirmation layout
omits complete cancellation and booked-party facts; its rendered Desktop version link exposes
labeled confirmation sections and a canonical property link. Mobile payment totals can exclude
mandatory city tax, so those headlines cannot authorize all-in monitoring totals.

Use a narrow scripted reader inside the same Browser Use host for the observed grouped layout.
Resolve fresh rendered anchors and their real ancestry through the existing action guard, bind the
current source and focus before replay, meter same-tab navigation and history returns, and recheck
safety after awaited operations. The separately qualified Desktop version action must preserve the
same opaque confirmation identity and path and only change the observed view parameter. Never
export a refreshed cookie snapshot from this reader: preserve the original mobile price session.
Single-room English confirmation sections produce typed optional facts through the existing
mapper/validator. Unsupported, approximate, missing, or conflicting facts remain unknown; a visited
page does not establish eligibility. A non-grouped layout retains the existing agent path. The
scripted reader does not switch adapters or create another browser, model budget, or retry episode.

A second independently reproduced constraint is the shared 15-action ceiling. Three accommodation
views with mobile-to-desktop navigation and history returns exhaust that allowance before the
second group; this happens with zero model calls. Six such details require 28 metered navigation
and return actions, plus entry navigation. Introduce a distinct inventory maximum of 40 actions.
Price requests retain their independent hard maximum of 15. An inventory-bearing coordinator job
has one cumulative 40-action allowance; subsequent price requests receive at most 15 and no more
than the residual allowance. All phases share the existing absolute 180-second deadline, computer
input limit, and dollar ceilings. No counter resets between inventory and price. Supplied lower
inventory limits remain binding. The bounds change is confined to read-only inventory and recorded
here under the user's explicit end-to-end implementation authorization; it is not a global price
or transaction guard relaxation.

Qualification must prove actual grouped coverage, complete-fact eligibility where the source is
unambiguous, positive-only persistence, original session preservation, residual budget enforcement,
and unchanged price limits. The exploratory walker failures are diagnostic prototype failures;
they are not accepted release evidence. Construction remains in progress until actual candidate,
quality, review, and final-image evidence is recorded.

The first full scripted candidate reached both groups and five detail views but exhausted the
absolute deadline while reloading intermediate mobile confirmations on history returns. Replace
those repeated one-entry returns with a single native history jump to the already observed parent.
The history resolver uses bounded actual browser history, verifies the latest earlier parent and
every skipped destination, and binds current URL/focus/session. The host performs fresh safety
checks and meters the jump once. No constructed parent URL is navigated. The absolute deadline
remains unchanged. Inline confirmation labels and delayed parent-card rendering are qualified
explicitly rather than treated as absent inventory.

The September 13 diagnostic replay exposed two actual DOM variants: an icon splits the visible
confirmation H1 text across text nodes, and later navigation repeats `Booking Details` before
`Communications`. Match unique rendered H1-H6 headings as whole elements, with the property anchor
strictly between the confirmed heading and Check-in. Parse booked-party composition only inside
the uniquely identified confirmation header; later menu labels cannot hide that evidence. Browser
DOM regressions exercise the real snapshot JavaScript, including fragmented headings, duplicate
visible headings and unrelated property links. Unsupported house composition remains unknown.

Timing showed confirmation navigation spending roughly 8-11 seconds per mobile/desktop page.
Keep Browser Use's normal NavigateToUrlEvent and watchdog path, using `domcontentloaded` instead
of the default `load` wait. The existing bounded reader then waits for the rendered confirmation
and detail sections. This avoids waiting for unrelated page resources without bypassing the host,
changing the shared deadline, or accepting identity/financial facts before their evidence exists.
The candidate must still demonstrate actual caller persistence and source-qualified eligibility.

Candidate 16 completed browser reading in 139,974 ms with six validated positives and zero
validator rejections. Persistence then rejected the entire refresh because a saved UPCOMING stay
was now CURRENT. Content-free comparison confirmed its check-in/out, property, reference, room,
and refund deadline were unchanged. This is an elapsed-date transition, not new financial authority.

Permit only date-corroborated forward lifecycle progression: UPCOMING to CURRENT/COMPLETED and
CURRENT to COMPLETED, bound to the same saved confirmation and identical complete stay dates,
using the trusted observation date. Preserve all other existing explicit-conflict checks and saved
financial facts. Merge the corroborated lifecycle and recalculate eligibility/projection so a
current stay cannot retain upcoming monitoring authority. Backwards, premature, identity-mismatched
or date-ambiguous transitions still conflict. No generic per-row conflict skipping is introduced.

After the DOM-content navigation wait, require one uniquely bound property anchor and consecutive
unchanged desktop snapshots before collecting facts. This avoids stopping on heading-only loading
skeletons while leaving unsupported optional facts unknown. Both refinements remain inside the
same browser episode, original deadline, caller scope and positive-only reconciliation.

Candidate 17 showed why whole-document settling is unsuitable: unrelated menus/promotions kept
changing and the run again exhausted its deadline. Readiness now requires actual parsed identity,
property and stay-date values plus two consecutive matching extracted-fact sets; optional facts
remain subject to the same parser. A failed desktop read no longer falls back to parsing the earlier
mobile snapshot. The deadline stays fixed.

The same replay exposed an auxiliary confirmation link with another token in a four-card trip.
When explicit status-bearing card count plus known non-hotel count exactly equals the observed
parent booking count, use those cards as the worklist and count auxiliary links separately. When
that corroboration is absent, unknown targets still require inspection. This does not infer absence,
account completeness, booking identity from a count, or monitoring eligibility. Regression tests
retain unknown-status detail inspection and verify six real detail visits instead of an extra alias.

Candidate 18 reached six accepted/discovered reservations with one eligible in 138,554 ms, but
still recorded an auxiliary seventh detail visit and one unresolved item. The root anchor's flattened
text concatenated a September 19 date with `4 bookings`, hiding the count from the line matcher.
Read the exact count from visible child elements and carry it as bounded optional metadata (integer
1–99). Only exact corroboration against status cards plus known non-hotels suppresses auxiliary
targets; absent or conflicting count evidence preserves unknown-link inspection.

The exact Special Requests notice concerns optional, availability-dependent requests. Excluding
that specific notice from the mandatory-charge warning check does not establish an all-in total:
the existing explicit final-pay statement, booked-party/date correspondence, and complete component
reconciliation remain required. The observed EUR 101.20 layout qualifies locally; other unknown or
conflicting charges do not. Final caller replay and the full gate remain pending after these changes.

### Caller-flow timeout and bounded phase allocation (2026-09-14)

Replay 19 succeeded at inventory (five active details, two completed cards, two eligible receipts)
but the normal invited-user price execution timed out. The configured route is consented-users
with Browser Use prices; absence of an owner-only canary qualification row is expected for this
caller. The shared 180-second job deadline starves price discovery after a roughly 140-second
grouped inventory scan. ADR-048 now supersedes the earlier shared-wall-clock design above: combined
check-now/scheduled operations have a fixed 360-second ceiling and each executor phase remains
limited to a fixed 180 seconds or the remaining operation time, whichever is smaller. All phases
share the same cost, action and visual ledger. Inventory-only requests stay at 180 seconds.
Shutdown admission is rechecked before price work. Fake-clock and stop-race tests plus the actual
caller replay and exact-image shutdown check must validate this change before release.

Replay 19 also reported one unresolved traversal despite all expected active/inactive cards being
accounted for. Fixed-code, content-free step diagnostics were added to distinguish navigation
recovery from missing reservation details on the next replay; no completeness claim is made.

### Explained trip-count mismatch (2026-09-14 replay 21)

Content-free shape capture proved one group has four hotel links for four bookings, while the
other has three hotel links plus a confirmed `cars.booking.com` anchor for four bookings. The
rendered car link follows `/my-booking/<numeric-id>` and does not contain the literal Rental car
label recognized by the original counter. Count only this exact HTTPS car-product host/path and
Confirmed card as non-hotel evidence, rejecting credentials, ports and alternate destinations.
Do not navigate it. This corrects coverage accounting without adding product support or changing
which hotel facts qualify. Explicitly unknown other destinations remain unresolved.

### Exact property mismatch evidence (2026-09-14 replay 21)

Both trusted and observed hotel names were exactly `AIRINN Vilnius Airport Hotel RENOVATED 2025`.
The confirmation reference was `https://www.booking.com/hotel/lt/airlnn-vilnius.en-us.html`;
the code-read current price URL was `https://www.booking.com/hotel/lt/airlnn-vilnius.html`.
The price validator rejected only the English presentation suffix. Introduce the narrow
English-path equivalence documented in ADR-048, retaining every other identity/offer gate and
rejecting other hosts, credentials, ports, unsupported locale suffixes, escaped or malformed
paths, changed country/slug, and nonmatching visible names. No model output or saved identity
is rewritten. Regression tests and actual caller replay are required.
