---
unit: 001-adaptive-model-policy
bolt: 041-adaptive-model-policy
stage: model
status: complete
updated: 2026-08-13T02:25:43Z
---

# Static Model - Adaptive Model Policy

## Bounded Context

The Adaptive Model Policy context decides whether a caller-scoped Anthropic model call may start,
which approved model role receives it, how the cost is reserved/reconciled, and whether a model/
prompt profile is qualified for production. It does not observe or operate the browser, interpret
Booking.com domain truth, notify incidents, resolve secrets, or decide that a browser step succeeded.

Inputs are typed recovery/interpretation/diagnostic roles, structured prior attempt outcomes,
remaining coordinator-job limits, caller key identity (opaque), and bounded token estimates. Outputs
are either an admitted `ModelAttemptPlan` or a specific terminal admission reason. All downstream
provider output remains untrusted.

## Domain Entities

| Entity | Properties | Business Rules |
|--------|------------|----------------|
| `AdaptiveModelPortfolio` | primary profile, escalation profile, price-table version, policy version | Primary is Sonnet 5; escalation is Opus 5; both are Anthropic; Fable/unknown profiles are invalid |
| `ModelAttempt` | attempt ID, job ID, caller ID, role, profile, trigger, ordered position, reservation, result, usage, latency | Attempt belongs to exactly one caller/job; order is append-only; one result/charge reconciliation maximum |
| `BrowserJobSpend` | job ID, kind, started time, USD limit, reserved amount, charged amount, Opus reserve | One coordinator admission owns one ledger; reserved plus charged exposure cannot exceed USD 1 |
| `DeploymentSpendDay` | UTC date, USD limit, reserved amount, charged amount, version | One aggregate per UTC deployment day; transactionally admits all callers; exposure cannot exceed USD 10 |
| `QualificationRun` | run ID, portfolio, fixture profile, run count, metrics, gate result, override | Live qualification never opens Booking.com; default gate is 9/10 correctness and zero prohibited actions |
| `QualificationOverride` | profile identity, owner decision, reason, created time | Owner-only, local, explicit, auditable; never silently created by runtime routing |

## Value Objects

| Value Object | Properties | Constraints |
|--------------|------------|-------------|
| `ModelProfile` | provider, model ID, role, prompt version, pricing key | Provider is Anthropic; model ID is an approved Sonnet 5 or Opus 5 identifier for its assigned role |
| `ModelRole` | recovery, interpretation, classification, diagnostic | Diagnostic role has no action authority; all roles are allowlisted |
| `EscalationTrigger` | category, source attempt, verifier state | Eligible: semantic no-progress, repeated invalid schema, rejected unsafe proposal when diagnosis remains safe, unresolved low confidence, unverified Sonnet exhaustion |
| `ModelStopReason` | provider auth/outage/rate limit, protected state, prohibited action, time, job cost, day cost, pricing unavailable | A conclusive stop is not eligible for model escalation |
| `TokenEnvelope` | bounded input estimate, maximum output tokens | Non-negative, explicitly bounded, and priced before admission |
| `UsdAmount` | exact decimal/microdollar integer | Non-negative; no binary floating point; arithmetic is deterministic |
| `CostReservation` | reservation ID, profile, maximum USD, state | Must fit both job/day ledgers atomically before a provider call starts |
| `ReportedUsage` | input tokens, output tokens, provider status | Charged once; missing/interrupted usage uses the full conservative reservation |
| `QualificationMetrics` | correctness, diagnosis accuracy, schema validity, prohibited actions, escalation rate, calls, latency, tokens, USD | No page/session/account content; gate fields are deterministic aggregates |
| `CallerKeyRef` | caller ID, funding mode, opaque key provenance | Never contains plaintext key; escalation cannot change caller/funding source |

## Aggregates

| Aggregate Root | Members | Invariants |
|----------------|---------|------------|
| `AdaptiveModelPortfolio` | primary/escalation `ModelProfile`, routing policy, price-table version | Exactly Sonnet 5 → Opus 5; no Fable or cross-provider route; diagnostic authority remains advisory |
| `BrowserJobSpend` | reservations and ordered attempts for one coordinator admission | Maximum USD 1 exposure; once an ambiguous DOM episode begins, preserve sufficient Opus diagnostic reserve until terminal/ineligible; no duplicate reconciliation |
| `DeploymentSpendDay` | all outstanding/completed reservations for one UTC date | Maximum USD 10 exposure across restart/callers; admission and reservation are transactional; old exhausted date cannot reopen on clock rollback |
| `QualificationRun` | fixture outcomes and optional owner override | Ten runs per required fixture; at least nine correct; zero prohibited actions; failed gate cannot be production-selected without recorded owner override |

## Domain Events

| Event | Trigger | Payload |
|-------|---------|---------|
| `ModelCallReserved` | Job/day ledgers atomically accept conservative exposure | attempt ID, job ID, caller ID, role/profile codes, reserved microdollars, UTC date |
| `ModelCallDenied` | Pricing, qualification, job, day, caller, or terminal policy rejects a call | job ID, role/profile codes, exact safe reason, remaining safe allowance |
| `ModelEscalated` | Eligible Sonnet quality failure selects Opus | job ID, named operation, allowlisted trigger, source attempt position |
| `ModelAttemptCompleted` | Provider result or interruption is reconciled | attempt ID, safe outcome, token counts or conservative flag, charged microdollars, latency |
| `DeploymentSpendDayOpened` | First call reservation for a new UTC date | UTC date, limit, price-table version |
| `QualificationCompleted` | Required replay runs finish | portfolio identity, aggregate safe metrics, pass/fail |
| `QualificationOverridden` | Owner explicitly accepts a failed/unavailable gate | profile identity, owner identity, safe reason, timestamp |

## Domain Services

| Service | Operations | Dependencies |
|---------|------------|--------------|
| `AdaptiveModelRouter` | select primary; classify Sonnet outcome; select Opus or exact stop | portfolio, ordered attempts, typed verifier/safety state |
| `ModelCostEstimator` | calculate conservative maximum and actual charge | versioned approved-model price table, token envelope/usage |
| `SpendAdmissionService` | reserve job/day exposure; preserve Opus allowance; reject exactly | browser-job aggregate, deployment-day repository, clock |
| `UsageReconciliationService` | charge actual once; conservatively charge missing usage; close reservation | cost estimator, job/day aggregates |
| `QualificationEvaluator` | aggregate fixture runs; apply correctness/safety gates; resolve explicit override | qualification repository, clock |

## Repository Interfaces

| Repository | Entity | Methods |
|------------|--------|---------|
| `DeploymentSpendRepository` | `DeploymentSpendDay` | `reserve_call`, `reconcile_call`, `get_day`, `remaining_for_day` |
| `ModelAttemptRepository` | `ModelAttempt` | `append_reserved`, `complete_once`, `list_for_job` |
| `QualificationRepository` | `QualificationRun`, `QualificationOverride` | `save_run`, `latest_gate`, `record_override`, `approved_profile` |

## Business Rules and Invariants

1. Sonnet 5 is always the first eligible profile; Opus 5 is the only escalation profile.
2. Fable, arbitrary model strings, and unpriced profiles fail validation before browser work.
3. A protected state, deterministic business rejection, provider-wide failure, or exhausted hard
   boundary cannot be overridden by escalation.
4. The same caller's key provenance is immutable throughout primary and escalation attempts.
5. A provider call starts only after both job and deployment-day conservative reservations commit.
6. One coordinator admission is one job ledger: `/bookings`; `/checknow` sync plus selected check; or
   one scheduled slot sync plus its admitted checks.
7. Job exposure is at most USD 1; deployment UTC-day exposure is at most USD 10.
8. During an ambiguous DOM episode, Sonnet cannot consume the reservation needed for one otherwise
   eligible Opus diagnostic turn. A known deterministic failure starts neither call.
9. Usage is charged exactly once. Missing or interrupted usage charges its conservative reservation.
10. Production selection requires a passed qualification or explicit locally recorded owner override.
11. Routing/audit fields never contain prompts, page content, provider reasoning, secrets, URLs, or
    reservation identity.

## Story Coverage

- **US-130**: `AdaptiveModelPortfolio`, `AdaptiveModelRouter`, escalation/stop value objects, ordered
  `ModelAttempt`, and caller-key invariant.
- **US-131**: `BrowserJobSpend`, `DeploymentSpendDay`, `CostReservation`, admission/reconciliation
  services, and persistent repositories.
- **US-132**: `QualificationRun`, metrics, evaluator, repository, gate, and explicit owner override.

## Ubiquitous Language

| Term | Definition |
|------|------------|
| Primary model | Sonnet 5 profile attempted first for eligible adaptive work |
| Escalation model | Opus 5 profile selected only after an eligible measured Sonnet quality failure |
| Quality failure | Typed evidence that the model response or verified progress is inadequate, distinct from a safety/provider/budget terminal |
| Diagnostic turn | Read-only, actionless model call producing a typed advisory terminal explanation |
| Coordinator job | One browser admission and all LLM calls belonging to its `/bookings`, `/checknow`, or scheduled-slot work |
| Conservative reservation | Pre-call maximum estimated USD exposure derived from bounded input and maximum output |
| Charged cost | Actual reported token cost, or conservative reserved cost when actual usage is unavailable |
| Deployment day | Persisted UTC date shared by all callers and keys for the USD 10 cap |
| Ordered attempt history | Append-only safe metadata showing which role/model ran, why, and how it ended |
| Qualified profile | Model/prompt pair that meets replay correctness and safety gates or has explicit owner override |
