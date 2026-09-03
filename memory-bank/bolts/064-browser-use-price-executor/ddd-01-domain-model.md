---
stage: model
bolt: 064-browser-use-price-executor
created: 2026-09-02T23:52:00Z
---

# Static Model: Browser Use Price Executor

## Entities

- **PriceExecutionJob**: Identified by execution ID and bound to one owner, booking, trusted query,
  session lease, executor selection, absolute deadline, action limit, and cost limit. It can produce
  exactly one terminal price-execution result.
- **BrowserUsePriceEpisode**: The bounded model/browser interaction within a price job. It tracks
  admitted model calls, physical actions, elapsed time, cost, terminal status, and cleanup without
  storing page content or reasoning.
- **PriceQualificationRecord**: Redacted evidence for one Browser Use price execution, including
  eligibility, accepted-observation outcome, optional human comparison, cost, duration, action
  count, and critical violations under a versioned executor policy.
- **PriceReplayRun**: An operator-authorized execution against isolated state. It records only the
  deployed revision, route, terminal result, accepted/rejected counts, usage, cost, duration, and
  process outcome.

## Value Objects

- **PriceExecutorSelection**: Closed value `browser_use` or `stagehand` for agentic routes. Browser
  Use is the default; selection applies to future jobs and never changes during one job.
- **TrustedPriceQuery**: Code-owned property reference/name, check-in/check-out, occupancy, and
  expected currency. These are the only values the browser agent may type.
- **OwnerBoundSessionLease**: Opaque one-job capability binding encrypted session material to the
  authorized owner and execution. Cookie values never cross the executor port.
- **ExecutionLimits**: Absolute deadline, action count, computer/model work, per-job cost, and
  deployment-day cost ceilings shared by the complete coordinator operation.
- **ModelViewPreflight**: Content-free outcome describing mobile-context readiness, browser
  attachment, destination admission, screenshot usability, semantic-state availability, and a
  closed rejection reason.
- **GuardedPriceAction**: One proposed click, visual click, scroll, trusted-value type, safe key,
  wait, or back action plus code-owned pre/post authorization evidence.
- **ObservedQueryFacts**: Untrusted visible property/date/occupancy/authentication/Genius evidence.
- **ObservedOffer**: Untrusted visible room label, explicit all-in total/currency, refundability
  status/text, and evidence completeness. It contains no equivalence or savings conclusion.
- **PriceExecutionUsage**: Exact action/model-call/token/cost/latency measurements with no content.
- **BrowserUsePricePolicyIdentity**: Versioned executor/prompt/model/guard identity that prevents
  Stagehand evidence from qualifying Browser Use.

## Aggregates

- **PriceExecutionJob** (aggregate root): Owns one executor selection, session lease, limits,
  preflight, agent episode, terminal result, and cleanup outcome. Invariants: no provider work before
  admission; at most one physical action per step; one harness per job; one terminal result; exact
  usage reconciliation; cleanup on every terminal path.
- **Browser Use Price Qualification** (aggregate root): Owns only redacted records for one policy
  identity. Invariants: Stagehand evidence is excluded; critical violations dominate aggregate
  metrics; owner canary and invited-user promotion apply distinct average-cost thresholds; promotion
  remains an explicit owner action.
- **Price Replay** (aggregate root): Owns an isolated state copy and one execution. Invariants:
  production bookings and notification transports cannot mutate; process success requires a
  BookSaver-accepted observation rather than merely a completed model run.

## Domain Events

- **PriceExecutorSelected**: A future price job resolves Browser Use or Stagehand after routing and
  authorization.
- **ModelViewRejected**: Preflight proves a closed unusable/authentication/challenge/transport state
  before paid inference.
- **PriceObservationSubmitted**: Browser Use submits typed untrusted query/offer evidence.
- **PriceObservationAccepted**: BookSaver validation accepts at least one complete refundable
  all-in offer after query verification.
- **PriceExecutionFailedClosed**: The job terminates without price authority or same-job fallback.
- **PriceQualificationRegressed**: A critical violation or repeated invalid result disables broader
  Browser Use routing under the existing regression policy.
- **PriceReplayCompleted**: Isolated deployed execution terminates with an accepted or rejected
  BookSaver result and corresponding process exit.

## Domain Services

- **PriceExecutorResolver**: Combines route admission with configured executor selection; manual and
  scheduled triggers resolve identically after authorization.
- **BrowserUsePriceActionGuard**: Authorizes only bounded read-only actions, exact trusted typed
  values, and allowed pre/post destinations.
- **PriceObservationValidator**: Existing BookSaver service that independently verifies query facts,
  evidence completeness, currency, all-in status, and refundability before equivalence/savings.
- **PriceQualificationEvaluator**: Evaluates policy-versioned owner evidence against reliability,
  correctness, safety, privacy, cost, duration, and explicit-promotion gates.
- **PriceReplayRunner**: Obtains the normal coordinator/browser lease for isolated state, disables
  notifications and authoritative mutation, waits for terminal execution, and maps acceptance to
  process exit.

## Repository Interfaces

- **SessionLeaseBroker**: Issues and resolves owner/job-bound opaque session leases, then revokes
  them on cleanup.
- **DeploymentCostLedger**: Reserves and reconciles exact provider exposure across every terminal
  outcome without cross-thread SQLite reuse.
- **AgenticQualificationRepository**: Stores only policy-versioned redacted price-check evidence and
  promotion/regression state.
- **CheckTraceRepository**: Stores BookSaver check outcomes and content-free provenance, not model
  inputs or page evidence.

## Ubiquitous Language

- **Default executor**: The adapter chosen for an admitted future price job; not an emergency action
  selected after another adapter fails.
- **Explicit rollback**: Operator configuration that changes the executor used by future jobs.
- **Same-job fallback**: Starting a second browser harness after the first terminates; prohibited.
- **Model-visible state**: The screenshot and/or semantic representation actually supplied to the
  agent, distinct from an independently healthy CDP page.
- **Accepted observation**: Typed executor evidence that passes BookSaver validation; it is not yet
  an equivalent room or savings notification.
- **Production-equivalent replay**: Read-only execution of deployed wiring with an owner session and
  isolated state, waiting for the same terminal validation boundary as production.

## Story Coverage

- **US-164**: PriceExecutorSelection, PriceExecutorResolver, PriceExecutorSelected.
- **US-165**: PriceExecutionJob, BrowserUsePriceEpisode, GuardedPriceAction,
  BrowserUsePriceActionGuard, observed evidence, and usage.
- **US-166**: ModelViewPreflight and ModelViewRejected.
- **US-167**: BrowserUsePricePolicyIdentity, qualification aggregate/evaluator, and explicit
  rollback language.
- **US-168**: PriceReplay aggregate, runner, repository boundaries, and completion event.
