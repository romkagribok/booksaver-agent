---
intent: 026-jev-price-comparison
phase: inception
status: draft
created: "2026-09-26T16:29:30Z"
updated: "2026-09-26T16:29:30Z"
---

# Paired execution and Telegram contract

## Frozen experiment definition

Mode is baseline-only by default; paired mode selects Browser Use/Anthropic and Jev as two named
profiles. The initial window is 5–7 days of ordinary eligible checks for all admitted owner/invitee
users, with one pair per existing scheduled/manual check, not a randomized split of users between
methods. No synthetic production bursts. Persist model, adapter, prompts, price table, extraction,
validation and configuration versions; a behavior change opens a new cohort.

## Proposed persistence model

Use existing SQLite migrations and repositories; final column names belong to the DDD design.

- PriceComparison: opaque ID, user/booking IDs, trigger and schedule/manual dedupe key, experiment
  cohort, immutable booking-input fingerprint, opaque starting session revision, order, timing/gap,
  aggregate budget and common inventory-run identity/cost references. Never persist raw cookies or credential IDs.
- MethodRun: comparison ID + method unique key; pending/running/terminal state, dispatch identity,
  terminal reason, independently validated result, provenance, elapsed time, cost certainty and
  admission/actual usage references. Retain all failures and not-run reasons.
- ComparisonDelivery: comparison/user/booking identity, report version, pending/sending/sent/unknown
  status, Telegram message reference if known, bounded retries. Purge and access revocation apply.

Persist each transition before outbound work. On restart finalize an interrupted unknown arm as
interrupted/usage-unresolved; keep conservative cost reservations and the successful sibling. Do not
replay an unknown billable attempt just to complete the pair. A future normal check starts a new pair.
Canonical baseline application is idempotent against its execution ID and may happen once after the
pair's starting snapshots are fixed. Candidate does not touch ordinary failure history, key notices,
reconnect state, canonical savings, inventory reconciliation or session-vault updates.

## Execution sequence

1. Existing owner/invitee, inventory, booking/session and disclosure checks run once. Inventory stays
   on its current implementation and is not a Jev discovery experiment.
2. Create pair and both pending arms; freeze trusted booking inputs and session snapshot references.
3. Admit method-specific budgets with a hard aggregate cap. Persist balanced/randomized order before
   running anything. Each method also has its own action/call/time ceiling; cheap tokens do not grant
   unlimited browsing. Reserve baseline capacity so candidate spending cannot consume it first.
4. Under the sole coordinator/browser lease, run first arm in a new authenticated mobile context;
   verify evidence, persist terminal outcome, close browser and confirm cleanup.
5. Recheck access/revocation and deadline, then run the other arm from the original frozen inputs in
   another new context. An ordinary provider/model failure in arm one does not skip arm two. Global
   shutdown, lost authority, cleanup failure or exhausted pair limits stop it with an explicit reason.
6. Apply baseline canonical effects once, retain both comparison outcomes, and enqueue the report.
   A successful candidate with failed baseline remains informational; it cannot repair canonical state.
7. Release the lease only after child cleanup. Send/retry reports outside browser execution using
   persisted delivery state. Recheck recipient access before delivery.

Shared preflight failure before admission is not a valid paired observation: report why no price
check could run. Once a logical pair exists, both arm results must be present, including not-run.
Expired or revoked work cannot be resumed because a provider is cheap.

## Cost and limits

One logical pair consumes one daily price-check slot. All model calls, including retries and failures,
consume the governed call and spending budgets. Do not double-count shared inventory; display it
separately. Each shared refresh has a unique inventory-run ID; actual cohort spend counts that
refresh exactly once regardless of its booking count. After shared preflight, freeze the set of N
admitted booking pairs for that refresh and allocate 1/N of its cost to each pair's stand-alone
method estimate. Use rational/high-precision amounts with a deterministic final rounding remainder
so allocations sum to the original charge. Keep failed/denied method arms in the allocated set;
preflight-excluded bookings are reported separately and never secretly change N later. If N is zero,
retain the full refresh charge as unallocated prerequisite overhead in actual totals.

Report three distinct totals: actual experiment spend = both method arms + common cost once;
hypothetical baseline-only cost = baseline arms + common cost once; hypothetical Jev-only cost =
Jev arms + common cost once. These are estimates using the shared existing discovery workflow,
not measured independent all-Jev product runs. Never sum the two hypothetical totals as actual
spending. Tests cover multi-booking refreshes, failures, exclusions and zero admitted pairs.

Keep current baseline limits. Define Jev call/action envelopes during the feasibility bolt, persist
them in the experiment profile, and qualify them instead of silently inheriting an unsuitable chat
call count. Deployment must set a finite experiment cap within existing global spending limits;
missing caps keep paired mode disabled. Revalidate price metadata before activation.

Per price arm: at most 180 seconds including governed browser cleanup. Per pair: at most 360 seconds.
Explicit proposed inventory-plus-pair bound: 540 seconds for the existing combined operation unit;
construction must map this to multi-booking batching without multiplying the parent allowance by
booking count. If the parent residual allowance cannot fund another pair, report not-run rather
than resetting deadlines. This is a mode-specific ADR amendment, not a global timeout increase.

## Telegram presentation

One final comparison report per booking/check, two rows regardless of result. This is two results,
not two independent alert pipelines. Prefer final report after both terminals; an optional pending
message must be updated using the same identity rather than producing unbounded progress messages.

Illustrative format only (invented amounts, not observed results):

```text
Price check · Example Hotel · Oct 12–15

Existing method: $480 total · no lower equivalent offer
AI cost: $0.084 · 62s

Jev (experimental): $465 total · $15 potential savings
AI cost: $0.0034 · 41s

Both offers passed the same checks. Observed 1 minute apart.
Shared booking refresh cost: $0.012
Comparison: ABC123
```

For failure use "Jev (experimental): Could not verify refundability" with cost/time, not a guessed
price or "no savings". Show unverified price only if the established product policy permits it;
default is omit it. Use total-stay currency-aligned amounts; include enough room/refund evidence to
explain disagreements. Costs are USD and visibly distinct from booking currency; use sufficient
precision (or '< $0.0001'), and label conservative/unknown usage. Report valid no-offer outcomes
separately from incompleteness. Scheduled checks also send these reports during paired mode.

Baseline savings events still persist once. Integrate the normal Telegram savings content in the
comparison report and suppress only its redundant Telegram send. Keep email semantics unchanged.
Candidate savings appear only as validated experimental information; no booking action/rebooking
workflow is offered. Failed Telegram delivery does not rerun browsers. An ambiguous send is marked
unknown; stable comparison IDs and bounded reconciliation mitigate duplicates without claiming
network-level exactly-once delivery.

## Analysis and decision

Report counts for requested checks, shared-preflight exclusions, admitted pairs, each arm outcome,
paired completions, and mismatched evidence. Main success is an independently validated complete
price outcome (including conclusive no-equivalent-offer), not merely model DONE or a cheap stop.
Show total method spend / all assigned arms and total spend / verified successes, including failed
attempts and conservative charges; also show known-only sensitivity and unresolved spend.

Break down model and end-to-end p50/p95, provider waits, browser occupancy, queue/busy outcomes,
missed scheduled slots, action counts, token counts, and guard rejections. Compare matched pairs,
stratify property/user/trigger/order, and cluster repeated checks by booking/property. Review divergent
prices/refundability/authentication with sanitized evidence and observation timestamps; site movement
is not automatically a model error. A small repeated hotel sample cannot establish general reliability.

Owner decision options: continue collecting within caps, keep baseline, promote Jev for price only,
or reject Jev. Suggested targets from the earlier plan (50% lower all-in cost per verified success,
no more than 5 percentage points success regression, no material latency regression) are proposals,
not automatic gates or proof from a small sample. Zero safety/isolation incidents is mandatory.
Stagehand retirement, broader cleanup and inventory conversion require their own subsequent decision.
