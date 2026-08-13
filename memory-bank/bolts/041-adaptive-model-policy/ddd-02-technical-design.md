---
unit: 001-adaptive-model-policy
bolt: 041-adaptive-model-policy
stage: design
status: complete
updated: 2026-08-13T02:26:50Z
---

# Technical Design - Adaptive Model Policy

## Architecture Pattern

Extend BookSaver's existing hexagonal architecture with a provider-neutral adaptive model-policy
domain and two driven ports: a model-call executor/factory and a transactional spend repository.
Workflow modules ask the policy for an admitted attempt; they do not select model strings, estimate
prices, access SQLite, or borrow credentials.

The design amends ADR-017's call-count-only caps and ADR-030's single-profile recovery while
preserving ADR-021's sole `CheckCoordinator` admission boundary, ADR-019's caller-key isolation, and
all existing browser/domain verification authority.

```text
CheckCoordinator admission
        |
        v
BrowserJobCostBudget -----> SpendLedger port -----> SQLite transaction
        |
        v
AdaptiveModelSession -----> ModelPortfolio -----> Sonnet 5 primary
        |                                      `-> Opus 5 escalation
        v
role adapter (agent / classifier / interpreter / extractor / diagnostic)
        |
        v
Anthropic SDK call -----> usage reconciliation -----> job + UTC-day ledgers
```

## Layer Structure

### Domain

- Add explicit model-policy types for approved profiles, roles, escalation triggers, attempt
  outcomes, stop reasons, token envelopes, exact USD amounts, reservations, and qualification gates.
- Keep these types free of Anthropic SDK, SQLite, Telegram, Playwright, and configuration parsing.
- Validate portfolio invariants at construction: Sonnet 5 primary, Opus 5 escalation, no Fable,
  no unknown/unpriced identifier.

### Application

- `AdaptiveModelSession` owns ordered attempts for one recovery/interpretation/diagnostic episode.
- `BrowserJobCostBudget` spans one `CheckCoordinator` admission and is passed to synchronization plus
  all price checks within that admission.
- Add Protocol ports for transactional spend reservation/reconciliation and qualification lookup.
- Extend model-role factories to build caller-scoped Sonnet and Opus adapters using the same opaque
  key provenance; never resolve a second user's/owner key during escalation.
- Once an ambiguous DOM episode is admitted, preserve one Opus diagnostic reservation until the
  episode becomes ineligible or terminal. Known deterministic failures create no model session.

### Infrastructure

- Anthropic adapters accept an approved `ModelProfile`; model selection remains outside prompt code.
- SQLite stores deployment-day exposure and individual call reservations transactionally.
- Configuration loads the fixed portfolio and dollar ceilings, normalizes documented legacy defaults,
  rejects Fable/unknown custom values, and never contains credentials.
- Replay reporting consumes the same routing/cost policy through fakes or explicit live adapters.

### Presentation and Operations

- `config show`/`config validate` expose safe portfolio role names, price-table version, and dollar
  ceilings.
- Replay output shows ordered attempts and aggregate model/cost metrics without prompt/page data.
- Later bolts attach ordered attempt metadata to browser outcomes and incident notices.

## Application Contracts

### `ModelPortfolio`

```text
primary(role) -> ModelProfile(Sonnet 5)
escalation(role) -> ModelProfile(Opus 5)
validate() -> None or configuration error
```

The portfolio is fixed to approved identifiers/aliases shipped with BookSaver. A profile must have a
price-table entry and compatible capability metadata (vision/tool use/typed response as required).

### `AdaptiveModelSession`

```text
start(task_role, caller_key_ref, browser_job_budget) -> attempt plan
record_outcome(attempt_id, typed outcome) -> next attempt plan or exact stop
ordered_attempts() -> safe attempt audit
```

Eligible escalation triggers:

1. semantic no-progress after evidence-rich reorientation;
2. two invalid typed/schema responses;
3. rejected unsafe proposal while the step remains safely recoverable/diagnosable;
4. unresolved low-confidence/unknown classification;
5. exhausted Sonnet recovery without deterministic verification.

Ineligible stops include confirmed authentication/MFA/captcha/bot wall, prohibited/protected
destination, deterministic business rejection, provider authentication or deployment-wide outage/
rate limit, caller revocation, unavailable current observation, pricing/time/job/day exhaustion.
They return directly with zero model calls when deterministic evidence is conclusive.

### `SpendLedger`

```text
reserve(job_id, caller_id, utc_date, profile, role, token_envelope) -> reservation | exact denial
reconcile(reservation_id, reported_usage | unavailable, latency, outcome) -> charged cost
remaining(job_id, utc_date) -> safe job/day allowance
```

- Reservation and deployment-day aggregate update occur in one immediate SQLite transaction.
- `reserved + charged` exposure is compared in integer microdollars/`Decimal`, never float.
- Reconciliation is idempotent by reservation ID.
- A stale in-flight reservation remains conservatively charged after restart; no cleanup reopens cost.
- Unknown price/model fails before provider invocation.

### `QualificationRepository`

```text
record_run(profile_pair, prompt_versions, fixture_metrics) -> gate result
latest_gate(profile_pair, prompt_versions) -> qualified | rejected | missing
record_owner_override(owner_id, safe reason) -> approved override
```

## Coordinator Job Boundaries

- `/bookings`: one account synchronization job.
- `/checknow`: prerequisite synchronization plus the selected reservation price check.
- scheduled slot: prerequisite synchronization plus every eligible reservation check admitted for
  that user/slot.
- Any other browser admission must name a job kind explicitly before making an LLM call.

The coordinator creates/closes the job budget. Nested recovery, extraction, and interpretation
receive the same budget object and cannot create a new USD 1 allowance.

## Data Persistence

Use an additive schema-v14 migration.

### `llm_spend_days`

| Column | Type / Constraint | Purpose |
|--------|-------------------|---------|
| `utc_date` | TEXT PRIMARY KEY | Deployment-wide UTC accounting day |
| `reserved_micro_usd` | INTEGER NOT NULL CHECK >= 0 | Outstanding/conservatively exposed calls |
| `charged_micro_usd` | INTEGER NOT NULL CHECK >= 0 | Reconciled provider cost |
| `limit_micro_usd` | INTEGER NOT NULL CHECK = 10000000 | Historical enforced day ceiling |
| `price_table_version` | TEXT NOT NULL | Pricing basis for audit |
| `updated_at` | TEXT NOT NULL | Safe operational timestamp |

### `llm_cost_reservations`

| Column | Type / Constraint | Purpose |
|--------|-------------------|---------|
| `reservation_id` | TEXT PRIMARY KEY | Idempotency and reconciliation key |
| `job_id` | TEXT NOT NULL | One coordinator admission |
| `caller_user_id` | INTEGER NOT NULL | Existing local caller scope; never emitted in incident/log payloads |
| `utc_date` | TEXT NOT NULL REFERENCES `llm_spend_days` | Day aggregate |
| `attempt_ordinal` | INTEGER NOT NULL CHECK >= 1 | Ordered safe audit |
| `provider`, `model`, `role`, `trigger` | bounded TEXT CHECK values | Allowlisted attempt metadata |
| `reserved_micro_usd` | INTEGER NOT NULL CHECK >= 0 | Conservative pre-call exposure |
| `charged_micro_usd` | INTEGER CHECK >= 0 | Actual/conservative final charge |
| `status` | TEXT CHECK reserved/charged/conservative | Lifecycle |
| `input_tokens`, `output_tokens`, `latency_ms` | bounded INTEGER | Usage/latency audit; nullable until complete |
| `created_at`, `completed_at` | TEXT | Lifecycle timestamps |

Indexes cover `(utc_date, status)` and `(job_id, attempt_ordinal)`. Existing user purge removes
caller-linked reservation detail while retaining only aggregate day spend needed for the hard cap.

### `llm_profile_qualifications`

Stores profile/prompt/fixture-version identity, aggregate metrics, gate result, optional explicit
owner override and safe reason, and timestamps. It stores no fixture content or provider response.

## Cost Estimation

- Ship a versioned code-owned price table for the approved Sonnet 5 and Opus 5 identifiers.
- Apply Anthropic's published Sonnet 5 introductory price only through 2026-08-31 UTC and switch
  automatically to the published standard price on 2026-09-01, so a long-lived deployment cannot
  under-reserve after the promotion ends.
- Normalize aliases to a price-table identity before admission.
- Bound text, structure, image dimensions/bytes, history, and maximum output at the role adapter.
- Calculate a conservative input-token upper bound from those enforced limits, including the vision
  allowance, then reserve full maximum output cost.
- Reconcile with Anthropic-reported input/output usage. If usage is missing or the call is interrupted,
  charge the reservation maximum.
- If actual usage unexpectedly exceeds the reservation, charge actual, emit a safe invariant event,
  and deny later calls. Tests prove configured bounds make this path unreachable under normal SDK use.

## Configuration

Extend `[agent]` with validated non-secret settings:

```toml
primary_model = "claude-sonnet-5"
escalation_model = "claude-opus-5"
max_job_cost_usd = "1.00"
max_deployment_daily_cost_usd = "10.00"
reserve_opus_diagnostic_for_ambiguous_episode = true
```

- Legacy `agent.model` and `extraction.model` defaults normalize to the primary profile during the
  documented migration; arbitrary or Fable values fail validation instead of silently routing.
- Dollar values parse through `Decimal`, have exact fixed upper bounds, and are displayed redacted-
  safe because they are not secrets.
- Credentials remain only in `BOOKSAVER_LLM_API_KEY` or encrypted personal-key storage.

## Security Design

| Concern | Approach |
|---------|----------|
| Caller isolation | Resolve one caller key reference before constructing both profiles; no fallback re-resolution |
| Portfolio injection | Closed model identifier enum/validator plus code-owned price/capability table |
| Prompt/page leakage | Attempt/cost stores accept only bounded enums, integers, safe IDs, and timing |
| Cost race | SQLite immediate transaction reserves day/job exposure before SDK invocation |
| Crash between reserve/call/reconcile | Outstanding reservation stays conservatively exposed across restart |
| Safety override | Router receives code-owned terminal/safety state and cannot escalate it away |
| Owner override | Explicit owner-only local record; never model-created; visible in qualification output |

## Error Handling

| Error Type | Domain Result | Behavior |
|------------|---------------|----------|
| Unapproved/Fable model | `model_not_approved` | Config validation fails before browser work |
| Missing model price | `model_pricing_unavailable` | No provider call |
| Job allowance exhausted | `job_cost_limit` | No provider call; caller-safe retry/action |
| Deployment day exhausted | `daily_cost_limit` | No provider call; include next UTC reset safely |
| Caller key invalid/revoked | existing caller-specific key reason | No owner/global key fallback |
| Anthropic provider-wide terminal | `provider_unavailable` or exact safe subtype | No ineffective Opus retry unless failure is model-specific and policy permits |
| Invalid response | quality outcome; Opus after threshold | Final invalid-provider reason if Opus also fails |
| Reconciliation conflict | `cost_accounting_error` | Fail closed for later calls; preserve reservation exposure |
| Qualification missing/failed | `model_profile_unqualified` | Reject production selection unless explicit owner override |

## NFR Implementation

| Requirement | Design Approach |
|-------------|-----------------|
| USD 1/job and USD 10/day | Transactional conservative reservations in integer microdollars |
| Restart safety | SQLite day/reservation state; reserved calls never auto-refund |
| Deterministic happy path | No model session or cost reservation until deterministic step requests assistance |
| Bounded escalation | Closed trigger/stop types and one-way Sonnet → Opus state machine |
| Auditability | Ordered attempt metadata with exact provenance and no content |
| Testability | Inject clock, price table, spend repository, profiles, provider outcomes, and token envelopes |
| Compatibility | Explicit config normalization/error messages and additive schema migration |

## Test Design

- Pure domain tests for portfolio validation, trigger eligibility, one-way escalation, stop precedence,
  exact money arithmetic, Opus reserve, and qualification gates.
- SQLite integration tests for atomic concurrent reservation, idempotent reconciliation, restart,
  UTC rollover/rollback, migration, purge, and overrun handling.
- Factory/config tests for fixed profiles, legacy normalization, Fable/unknown rejection, caller key
  reuse, missing access, and safe config output.
- Anthropic fake tests for ordered role/model calls, usage reconciliation, provider errors, and no
  hidden content in attempt records.
- Replay tests for metrics, 9/10 and zero-prohibited-action gates, failed-profile rejection, and
  explicit owner override.

## ADR Analysis

Create ADR-031 to amend ADRs 009, 017, 021, and 030 with the fixed Sonnet/Opus portfolio,
quality-triggered escalation, coordinator-job budget semantics, transactional deployment-day spend,
and qualification gate. These decisions are cross-cutting and must remain discoverable for every
future model, recovery, usage-accounting, or provider change.
