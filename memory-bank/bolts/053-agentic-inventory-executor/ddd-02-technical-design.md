---
stage: design
bolt: 053-agentic-inventory-executor
created: 2026-08-26T03:42:00Z
---

# Technical Design: Agentic Inventory Executor

## Architecture Pattern

Extend the existing hexagonal browser-executor architecture with a separate inventory capability.
The adapter owns semantic/visual perception; the application service validates typed evidence; the
domain owns positive-only reconciliation and fresh-run check admission. The legacy inventory parser
is not wrapped or called as a recovery tier.

## Layer Structure

```text
Telegram / scheduler / post-connect
              |
      CheckCoordinator (one gate, job, deadline, cost/action allowance)
              |
     InventoryExecutionService
              |
       InventoryBrowserExecutor port
              |
   StagehandInventoryBrowserExecutor
      | semantic observe/guard/replay/extract
      ` guarded Anthropic computer use
              |
       InventoryObservationValidator
              |
 Positive-only account reconciliation
              |
 Current-run receipt -> optional price check
```

## Domain and Application Modules

- `domain/inventory_executor.py`
  - `InventoryExecutionRequest`, `InventoryExecutionResult`, `InventoryExecutionStatus`.
  - `ObservedInventoryScope`, `ObservedReservation`, and inventory evidence states.
  - Terminal invariants excluding session/page content and rejecting contradictory evidence.
- `application/ports.py`
  - `InventoryBrowserExecutor` protocol beside `PriceBrowserExecutor`.
- `application/inventory_executor.py`
  - `InventoryExecutionService`, `InventoryObservationValidator`, and fake executor.
  - Maps accepted positive evidence to existing `ReservationObservation` values.
  - Always requests positive-only reconciliation; executor claims never become absence authority.
- `application/browser_executor.py`
  - Generalize the non-persisted session lease binding from booking-specific to capability-neutral
    subject identity while keeping owner and one-use checks.

## Infrastructure Adapter

- Add `infrastructure/browser/agentic_inventory_executor.py`.
- Reuse the existing async runner, transient Chromium lifecycle, session injection/read-back,
  execution meter, cost budget, redacted provenance, and provider usage mapping.
- Inventory runtime navigates only to the code-owned account entry URL, extracts one typed page
  observation, and lets BookSaver select the next required scope, page, or detail task.
- Stagehand proposes each semantic action; generic element inspection plus an inventory-specific
  guard validates it before deterministic replay and post-destination validation.
- On first semantic failure, one inventory-specific Anthropic computer-use episode can submit typed
  observations or a closed terminal. TYPE is not exposed.
- Browser/profile teardown is unconditional. Cookie refresh remains eligible only after the existing
  two-probe code-owned authentication verification and session compare-and-replace.

## Inventory Contracts

### Request

- execution ID and owner user ID;
- fixed required scopes: upcoming, past, cancelled;
- opaque session lease bound to `account:<owner-user-id>`;
- one absolute deadline;
- remaining total actions, computer actions, and cost.

### Result

- closed terminal status and observed authenticated context;
- tuple of typed scope observations;
- tuple of typed positive reservations;
- redacted provenance and refresh eligibility;
- action/token/cost usage, latency, fallback flag, and safety violations.

The result cannot contain cookies, screenshots, page text, accessibility trees, selectors, prompts,
reasoning, provider SDK objects, eligibility, or authoritative completeness/absence conclusions.

## Validation and Reconciliation

1. Validate request/result execution and account binding.
2. Reject missing or conflicting stable remote identities.
3. Merge duplicate identity evidence only when lifecycle, property, and dates do not conflict.
4. Map explicitly supported facts; unknown facts remain `None` and therefore ineligible.
5. Reuse BookSaver eligibility evaluation for lifecycle, dates, room, occupancy, booked all-in total,
   currency, explicit refundability, and cancellation deadline.
6. Reconcile as incomplete/positive-only even when traversal coverage appears terminal, thereby
   preserving every unseen row.
7. Query monitoring projections whose account row has `last_sync_run_id == current run_id`; only
   those booking IDs can proceed in `/checknow` or scheduled work.

## Trigger Orchestration

- `/bookings`: run one agentic inventory sync and render accepted current positives together with
  clearly labeled preserved last-safe rows.
- `/checknow` without an argument: render the saved caller-owned picker without browser work.
- Selected `/checknow`: acquire one coordinator job, run inventory once, require a matching
  current-run receipt, then run price execution with the same job ID, residual cost/action allowance,
  and absolute deadline.
- Scheduler: run inventory once, then check only current-run positive monitoring projections under
  the same job boundary.
- Post-connect: retain server-backed authentication finalization, then invoke the ordinary agentic
  inventory capability.

## Routing and Configuration

- Add capability-specific inventory routing with `agentic` as the default and `legacy` as rollback.
- Price `routing` remains unchanged and owner-canary in production.
- Agentic inventory requires active authorization, a valid session, an LLM key, and current
  disclosure consent for invitees.
- A terminal agentic result does not invoke the legacy parser in the same job.
- Critical safety/privacy/session outcomes are independently observable and can trigger or support
  an operator inventory rollback without changing price routing.

## Data Persistence

- Preserve existing account reservation and synchronization tables and their ADR-028 behavior.
- Add a schema-v17 content-free inventory execution record keyed by synchronization run and user:
  source, terminal status, accepted/rejected/scope/page/detail counts, semantic/computer actions,
  input/output tokens, micro-USD cost, latency, fallback flag, and safety codes.
- No content-bearing evidence is stored in the execution record.
- Repository support exposes booking IDs whose source reservation was positively observed in an
  exact synchronization run.

## Security Design

- Account session lease is owner-, subject-, and execution-bound and one-use.
- Inventory guard allows only visible/enabled read-only scope, pagination, and detail controls.
- Destinations are restricted to approved Booking.com inventory and confirmation route families.
- Modification, cancellation, reservation, payment, purchase, authentication, credentials, MFA,
  captcha solving, arbitrary URL navigation, files, clipboard, and shell remain impossible.
- Revocation is rechecked before reconciliation, before price continuation, and before completion
  delivery.

## NFR Implementation

- **DOM resilience**: No fixed Booking.com selector appears in the new inventory adapter; fixtures
  vary class/test ID/nesting/overlay/iframe/shadow/accessibility quality.
- **Cost**: Inventory and price share a persisted job ledger; residual limits are passed between
  phases and duplicate `/checknow` inventory is removed.
- **Time**: One absolute deadline spans inventory and price.
- **Privacy**: Egress is Booking.com, Anthropic, and loopback only; persisted telemetry is
  content-free.
- **Rollback**: Legacy inventory remains isolated behind capability-specific config.

## Test Strategy

- Domain contract and validator tests for binding, terminal invariants, duplicate conflicts,
  positive mapping, content exclusion, and limits.
- Persistence tests proving positive upsert, unseen preservation, exact current-run receipts, and
  redacted schema-v17 metrics.
- Adapter tests for semantic traversal, guards, visual handoff, terminal states, cookie verification,
  teardown, egress, and Docker launch.
- Cross-trigger tests for `/bookings`, post-connect, saved picker, selected `/checknow`, scheduler,
  invite disclosure, and independent rollback.
- Full Ruff, mypy, pytest, CLI/config smoke, AI-DLC status integrity, and exact-image Stagehand smoke.
