---
bolt: 041-adaptive-model-policy
created: 2026-08-13T02:29:33Z
status: accepted
superseded_by:
---

# ADR-031: Adaptive Sonnet/Opus Routing and Dollar Admission

## Context

ADR-030 established truthful, bounded, provider-neutral browser recovery, but production still uses
one configured browser model and separate extraction model. The current Booking.com incident proved
that an otherwise useful model conclusion can be collapsed into a generic result, and that a weak
model has no measured escalation path. ADR-017 limits calls/time, not dollars, while ADR-021's daily
counters reset on restart and are per user rather than a deployment-wide spend ceiling.

The operator wants BookSaver to spend more to recover genuinely ambiguous DOM drift, replace an
ineffective model automatically, and alert on maintenance-worthy changes. They explicitly approved
Sonnet 5 and Opus 5 and excluded Fable. They also clarified that predictable failures—such as a
conclusively expired session requiring `/connect`—must not incur an LLM explanation call.

## Decision

1. Use a fixed Anthropic portfolio: Sonnet 5 is the primary model for browser recovery,
   classification, interpretation, extraction, and ambiguous failure diagnosis; Opus 5 is the only
   escalation model. Fable and arbitrary/unpriced profiles are invalid for this capability.
2. Invoke LLM work only when deterministic current evidence cannot prove the postcondition or map to
   a known exact failure. Conclusive authentication/MFA/captcha/bot-wall, blocked destination,
   observation/provider failure, budget/time limit, and deterministic business rejection return
   immediately under their exact code with zero explanation calls.
3. Escalate Sonnet to Opus only after typed quality evidence: semantic no-progress after visual
   reorientation, repeated invalid schema, unresolved low confidence/unknown classification,
   rejected unsafe proposal while diagnosis remains safe, or exhausted Sonnet work without verifier
   success. A safety, provider-wide, caller, or hard-budget terminal cannot be escalated away.
4. Define one dollar-budget job as one `CheckCoordinator` browser admission: `/bookings`
   synchronization; `/checknow` synchronization plus its selected price check; or one scheduled
   slot's synchronization plus all checks admitted for that user. Every nested LLM role shares it.
5. Enforce USD 1 maximum estimated exposure per job and USD 10 maximum estimated exposure per
   deployment UTC day. Persist transactional conservative call reservations and reconciled usage in
   SQLite using integer microdollars/exact decimal arithmetic. Apply published UTC pricing effective
   dates automatically; unknown pricing fails closed.
6. Once an ambiguous DOM episode begins, preserve sufficient remaining job allowance for one
   otherwise eligible Opus diagnostic turn. A known deterministic failure opens no episode and
   reserves/spends nothing.
7. Resolve one caller key provenance before primary work. Opus uses the same caller/funding source;
   it never borrows the owner or another user's key.
8. Qualify model/prompt profiles with sanitized offline fixtures and explicit opt-in live replay.
   Required fixtures need at least nine correct outcomes in ten runs and zero prohibited actions.
   A missed gate requires an explicit, local, owner-audited override.

This ADR amends ADR-009's small independently configurable extraction-model default, ADR-017's
call-count-only cost control, ADR-021's restart-reset daily accounting limitation, and ADR-030's
single-profile step policy. It preserves their provider isolation, coordinator ownership,
deterministic verifiers, bounded actions, and privacy rules.

## Rationale

The fixed two-model portfolio makes runtime behavior and cost auditable. Quality-triggered Opus use
addresses genuinely weak primary-model behavior without paying the strongest-model price on normal
or predictable paths. Deterministic short-circuiting is both cheaper and more reliable when the
system already knows the answer. Transactional pre-call reservations are the only way to enforce a
restart-safe shared dollar ceiling before external cost is incurred.

### Alternatives Considered

| Alternative | Pros | Cons | Why Rejected |
|-------------|------|------|--------------|
| Ask an LLM to explain every failure | Uniform prose | Adds latency/cost and can distort already-conclusive facts | Predictable failures already have safer exact codes and actions |
| Use Fable as final escalation | Maximum model capability | Too expensive and unnecessary for bounded browser diagnosis | Explicitly rejected by the operator |
| Use Opus for every adaptive call | Simpler routing | Higher routine cost and no evidence that every turn needs it | Sonnet is the approved primary; escalation should be measured |
| Cross-provider failover | Provider-outage resilience | New credentials/adapters, different safety semantics, broader scope | Deferred; current request approves Anthropic-only portfolio |
| Keep arbitrary model strings | Easy experimentation | Unpriced/unsupported/Fable models defeat hard admission and qualification | Fixed validated profiles are required for safety and cost bounds |
| Keep only call/time caps | Minimal migration | Cannot enforce approved USD ceilings across different model prices | Dollar admission is an explicit requirement |
| Keep deployment spend in memory | Simple implementation | Restart reopens allowance and violates the hard daily cap | Persisted SQLite accounting is required |

## Consequences

### Positive

- Ambiguous DOM failures get a stronger model without paying Opus cost on predictable paths.
- Fable and unknown pricing cannot enter production accidentally.
- Worst-case admitted provider exposure is bounded per coordinator job and deployment UTC day.
- Spend and routing survive restart and remain caller-attributable.
- Future prompt/model changes have an explicit measurable release gate.

### Negative

- Configuration, provider factories, coordinator budget propagation, persistence, replay, and audits
  change together.
- Existing custom extraction/agent model strings must migrate to the fixed portfolio.
- Conservative reservation may stop a call that actual token usage would have fit.
- Opus access failure on a caller's personal key remains a terminal caller-scoped outcome rather than
  silently using owner billing.

### Risks

- **Pricing drift**: a stale table can understate cost. Mitigation: version the code-owned table,
  reject unknown IDs, expose the version, and update it during model upgrades.
- **Crash after reservation**: exposure may be charged without a completed call. Mitigation: retain
  reservation conservatively rather than risk reopening the cap.
- **Incorrect ambiguity classification**: deterministic known failure could invoke a model or an
  unknown DOM could terminate too early. Mitigation: typed step definitions, protected-state
  precedence, and production-shaped fixtures in bolts 042–043.
- **Profile quality regression**: model aliases/prompts can change behavior. Mitigation: replay gate
  and explicit owner override audit.

## Related

- **Stories**: US-130, US-131, US-132, US-133, US-134, US-135, US-136
- **Standards**: tech stack, system architecture, coding standards
- **Previous ADRs**: ADR-009, ADR-015, ADR-016, ADR-017, ADR-019, ADR-021, ADR-030
