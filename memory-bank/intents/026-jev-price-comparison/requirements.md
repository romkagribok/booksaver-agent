---
intent: 026-jev-price-comparison
phase: inception
status: construction
created: "2026-09-26T16:29:30Z"
updated: "2026-09-26T16:29:30Z"
---

# Jev price-check comparison

## Intent and user authorization

Build a complete Jev alternative to the existing price-check flow. For every eligible manual and
scheduled price check of each admitted user, execute both methods independently, record results
and costs, and send two labelled results in Telegram. Observe repeated runs over several days,
then let the owner decide whether to adopt Jev and separately retire obsolete alternatives.

On 2026-09-26 the user accepted the preceding plan with these corrections and explicitly requested
all AI-DLC documents on a new branch before handing implementation to another model. This turn
is documentation only. Implementation, tested merge, redeployment, and the paired experiment are
the requested eventual delivery scope; no implementation, commit, push, merge, paid request,
Telegram message, or deployment has occurred during inception. New artifacts are presented for
review, not represented as already reviewed. Construction starts when the user hands this package
to the implementing model. Keep the existing final-head Bugbot and operations gates.

## Business goals

| Goal | Measure | Priority |
|---|---|---|
| Compare complete methods | Two terminal method records for every admitted logical price check | Must |
| Make cost and success visible | Per-user Telegram comparison and owner-scoped aggregate report | Must |
| Avoid misleading cheap success | Independent validator, complete costs, explicit failures and missing evidence | Must |
| Preserve future choice | Baseline remains available; no automatic promotion or removal | Must |

## Functional requirements

### FR-1: Qualify the implementation approach

Assess Jev Ultrafast's useful components and Booking.com DOM coverage in an isolated spike before
committing to a library integration. Choose a small BookSaver-owned adapter using its indexed-action
design unless a pinned component demonstrably preserves all session, guard, budget, and extraction
contracts. Record an exact upstream revision/license for any reused code. Exit with fixtures proving
navigation AND grounded offer extraction are feasible, or an explicit blocked conclusion. No live
account traffic is needed for the first spike. **Must; US-204.**

### FR-2: Independent complete Jev price method

The candidate starts from the same trusted booking query as baseline, navigates independently,
collects its own query/property/room/rate/refundability evidence, and returns the existing typed
price contract through unchanged deterministic validators. Use only Jev for model inference inside
the candidate: no Anthropic navigation, extraction, classification, diagnostic, text helper, or
fallback. Trusted form values come from code; extraction selects observed spans/candidates and code
parses exact values. Missing facts or unsupported controls become explicit failures. A spy/egress
test proves no other model is called and no baseline page/evidence is consumed. **Must; US-207.**

### FR-3: Provider access and confinement

Call TypeSafe directly from the self-hosted daemon with a pinned version, bounded HTTP request,
explicit credential and endpoint allowlist. Propose BOOKSAVER_TYPESAFE_API_KEY as a separately
approved environment secret; update AGENTS/standards/config documentation during construction.
Fail closed on missing credentials, invalid response, unknown pricing, or version mismatch. Do not
send cookies, credentials, confirmation/PIN data, or unnecessary personal fields. Add a TypeSafe-
specific disclosure without silently migrating invitee acknowledgement. **Must; US-205.**

### FR-4: Guarded observations and actions

Observe relevant visible text and controls, build compatible safe candidate sets, and bind every
selection to a fresh observation. Recheck visibility, occlusion, destination, and target identity at
execution. Include blocked/unknown choices; stale observations cause bounded re-observation.
Confidence never bypasses guards or validators. No model selectors, arbitrary JS, generated URLs,
coordinates, or unsupported field values execute. **Must; US-206.**

### FR-5: Exact model spending

Extend provider/model/pricing identities and SQLite restrictions with forward migrations preserving
existing rows. Reserve before each provider attempt, account every retry, reconcile usage, and keep
conservative unknown-usage charges. Preserve sub-microdollar precision in reporting or documented
conservative rounding with raw usage; never round real spend to zero in the ledger. Every record
identifies arm, provider, model, pricing version, request outcome and cost certainty. **Must; US-208.**

### FR-6: Pair every admitted check

One comparison per eligible booking check for manual AND scheduled triggers; both implementations
are enabled during the experiment. Inventory discovery/refresh remains a single shared prerequisite.
Freeze booking inputs and starting owner session material, persist order, and run fresh independent
contexts under the sole coordinator/browser lease. Counterbalance order with a persisted random
assignment; record start/end times and gap. Eligibility still requires active access, current required
disclosure, session and inventory/booking admission. When a method cannot run, preserve its labelled
not-run/failure result. Never substitute one method's output for the other. **Must; US-209.**

### FR-7: Durable outcomes and isolated effects

Persist pair/arm identities and pending/running/terminal state before remote work. Candidate outputs
write comparison storage only; baseline alone updates canonical check history, savings, qualification,
failure counters and session-health effects, once. Never call the current side-effectful check job
twice. Revoke/delete wins over in-flight work; unknown interrupted requests are not blindly replayed.
A sibling's failure cannot erase a completed result. **Must; US-210.**

### FR-8: Explicit pair admission and limits

Count one logical pair toward daily check allowance; count all actual model calls and charges.
Maintain per-arm envelopes and a hard aggregate deployment cap; preserve capacity for both arms at
admission where possible. No automatic budget increase. Price arms each retain a maximum 180-second
execution ceiling; propose an explicitly versioned paired ceiling of 360 seconds, with an inventory-
plus-pair operation ceiling of 540 seconds where the existing combined unit is 360. Queue wait is
measured separately and cannot justify running an expired booking/schedule slot. This amendment
requires an ADR and production-load qualification. Global shutdown/regression/revocation wins;
resource denials become explicit arm outcomes, not silent sampling. **Must; US-211.**

### FR-9: Two results in Telegram for each user

For manual and scheduled checks, deliver one comparison report per booking/check containing two
clearly labelled method results, including valid price/currency or bounded failure reason, savings
when fully validated, observed time, elapsed time and model cost/uncertainty. Show Jev as experimental.
Use a durable delivery record and stable comparison ID; duplicate callbacks do not create duplicate
local sends. Handle ambiguous Telegram timeouts honestly (no absolute exactly-once claim). Reports
are sent even when no savings is found; no candidate reconnect/key-warning notification. Baseline
savings persistence remains once; suppress its redundant Telegram savings message when incorporated
in the report, while preserving existing email policy. No other user's data or owner-wide spend is
shown. **Must; US-212.**

### FR-10: Multi-day evidence and decision report

Record all assigned/admitted, completed, denied and failed arms. Produce paired success/cost/latency
reports with both unconditional and eligible-pair denominators, common inventory cost separately,
method-only and all-in costs, order/time gaps, authenticated/Genius provenance, failure classes,
disagreement review, busy rejections, and missed slots. Initial window is 5–7 days; no automatic extra
checks, retries or promotion to manufacture sample size. Freeze versions per cohort; owner decides
continue/adopt/reject using the evidence and its uncertainty. **Must; US-213.**

### FR-11: Pre-release qualification and live acceptance

Pass adversarial/local browser cases, caller isolation, side-effect isolation, accounting/migration,
restart/partial delivery, unchanged baseline/inventory regression, and isolated production-image
checks before activation. After gated activation, verify two actual native Telegram rows for an owner and a disclosed invitee and a scheduled
check. Simulated transport acceptance is distinct from native acceptance. No fabricated completed
DDD stages, tests or runtime evidence. **Must; US-214.**

### FR-12: Controlled delivery and reversible experiment

Implement defaults with paired mode disabled, then release through current-head review/Bugbot,
compatible migration/rollback checks and isolated image verification. Provision the TypeSafe key
without exposing it, set explicit caps and disclosure, and activate every eligible user's manual and
scheduled pairs. A kill switch stops new Jev arms and restores baseline-only future checks without
losing history; pending arms get cancelled/not-run terminals. Keep Stagehand and existing methods
until a later owner decision. **Must; US-215.**

## Non-functional requirements

| ID | Requirement | Acceptance |
|---|---|---|
| NFR-1 | Safety and privacy | Zero prohibited executed actions, cross-user records/messages, or secret-bearing fixtures/logs in qualification |
| NFR-2 | Independence | Candidate price execution makes zero non-Jev inference requests; no baseline evidence input |
| NFR-3 | Bounded execution | 180s per arm; 360s pair and proposed 540s inventory-plus-pair ceiling, including cleanup within the governed lease; no new phase after expiry |
| NFR-4 | Durable accounting | Every dispatched attempt reconciled or conservatively unresolved; crashes cannot release uncertain spend as zero |
| NFR-5 | Completeness | Exactly two arm terminal records per admitted pair after completion/recovery; one logical result-report delivery identity |
| NFR-6 | Fair measurement | Model/prompt/adapter/config versions, order, snapshot identity, timings and cost certainty recorded for every pair |
| NFR-7 | Operational recovery | Disabled mode preserves baseline behavior; staged kill-switch/restart test proves no orphan browser or duplicate canonical update |
| NFR-8 | Honest promotion | 5–7 days is an observation window, never a statistical pass; no promotion/removal without an owner decision |

## Scope exclusions and assumptions

- Inventory discovery, login/maintenance, Stagehand deletion, a universal model selector, BYOK,
  cloud browser services, new booking platforms, and rebooking actions are outside this intent.
- The Jev price method is complete; shared inventory may still use Anthropic and is attributed as
  common prerequisite cost, never hidden inside a claimed all-Jev product cost.
- Operational concurrency means both methods remain active, with browser work serialized in fresh
  contexts. True simultaneous browser workers would be a separate architecture change.
- Deployment access, TypeSafe credentials/account availability, account retention terms and remaining
  daily budget must be verified by operations; none were inspected or provisioned in this task.
- Cheap inference is a hypothesis, not evidence that browser occupancy, failure rate or maintenance
  cost is negligible. Cleanup remains a separate post-experiment scope.

## Traceability and review

See units.md for one-unit-per-FR ownership, experiment-design.md for state/Telegram semantics,
research.md for verified upstream sources, and implementation-handoff.md for the next model.
The detailed decomposition and proposed policy amendments are ready for user review.

## Amendment 2026-10-09: owner adoption decision

After six days and 56 paired checks the owner decided on 2026-10-06 to adopt Jev for price checks
and stop running the LLM price method in production, keeping its code as a rollback. This ends
the paired experiment early. Evidence is in `bolts/087-price-comparison-qualification/`.

### FR-13: Jev as the authoritative price method

`agentic_browser.price_executor = "jev"` selects Jev behind the unchanged price port. Its
validated result owns every canonical effect. No Anthropic price call is made. It requires its own
TypeSafe key, is bounded by the pinned model, per-check call cap and daily cost cap, records each
run's cost and diagnostic, and cannot be combined with paired mode. The Browser Use and Stagehand
price adapters stay selectable. **Must; US-217.**

### FR-14: Price discounted rate cards

Ground only the current price of a rate that shows an original and a current price; fail closed
when two unlabelled amounts are shown. **Must; US-216.**

### FR-15: Explainable Jev runs

Every Jev run keeps a content-free account of what it saw and chose, including why rates went
unpriced. **Must; US-218.**

### FR-16: Recover from the site's transient error page

When Booking.com serves its error page instead of the property, reload the trusted entry URL a
bounded number of times before any model decision. **Must; US-219.**

### Descoped by this decision

These parts of the original plan were not built and are no longer needed once the comparison ends.
They are recorded as descoped, not as delivered:

- FR-5: TypeSafe spend in the Anthropic reservation ledger with table migrations. Jev spend lives
  in its own nano-USD records with a daily cap instead.
- FR-8: sharing one inventory cost across pairs (1/N allocation) and the 540 s combined ceiling.
- FR-9: merging the savings alert into the comparison report and a retrying delivery outbox.
- FR-3: a TypeSafe-specific in-bot disclosure. Invitee inclusion was the owner's explicit choice.
- FR-10: percentile latencies, uncertainty intervals and stratified cohort statistics. A summary
  report with per-booking outcomes was produced instead.
- FR-11: a dedicated adversarial browser fixture suite and restart-negative tests on the exact
  image. Unit regressions, exact-image smoke and a production-snapshot stage probe were run.
