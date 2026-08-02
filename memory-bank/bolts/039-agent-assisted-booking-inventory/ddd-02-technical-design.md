---
stage: technical-design
bolt: 039-agent-assisted-booking-inventory
created: 2026-08-02T18:41:40Z
status: complete
---

# Technical Design: Agent-Assisted Booking Inventory

## Architecture Pattern

Extend the existing account-inventory adapter through constructor-injected recovery capabilities.
`CheckCoordinator` remains the only browser-admission and caller-accounting boundary;
`SynchronizeBookingAccount` remains the application use case; SQLite reconciliation remains the
authority for partial versus complete mutations.

```text
/bookings | /connect | /checknow | scheduled slot
                    |
             CheckCoordinator
          caller session + daily budget
                    |
       SynchronizeBookingAccount
                    |
 BookingComAccountInventorySource
       | deterministic first
       +-- BrowserAgent for named navigation drift
       +-- InventoryInterpreter for typed positive evidence
                    |
    SQLite reconciler (ADR-028 completeness gate)
                    |
        caller-scoped Telegram result
```

## Component Design

### Inventory Source

- Retain the existing bounded pending/visited traversal and deterministic HTML/JSON parsers.
- Wrap failed entry, scope, pagination, and detail operations with stable recovery labels and
  operation-specific verifiers.
- Discover redesigned visible scope controls through the shared observation and recover each
  missing required scope independently.
- Invoke interpretation only for unsupported or extraction-ambiguous current pages.
- Convert recovered observations back into bounded page content for deterministic reprocessing.
- Keep maximum page/reservation limits authoritative.

### Inventory-Specific Browser Guard

- Delegate to the shared adapter/controller ActionGuard.
- Additionally reject account mutation, sign-in, payment, checkout, reserve/rebook, and true
  cancellation actions.
- Permit read-only history controls whose label describes the `Cancelled` reservation scope.
- Refuse non-Booking.com and unallowlisted Booking.com destinations before execution or result.

### Interpreter

- Use the explicit caller-scoped factory role `inventory_interpreter`.
- Accept bounded visible page text plus sanitized Booking.com source URL.
- Parse a JSON array into typed observations; reject absence, unsafe source, duplicate identity,
  malformed dates/money/occupancy, and conflicting identities.
- Flag negative model claims as non-authoritative; the source accepts only upcoming, non-negative
  positive observations and never lets them overwrite deterministic facts.

### Usage Accounting

- Lazily resolve the navigation brain/interpreter only after deterministic failure.
- Consume the shared `AgentBudget` and active caller's `DailyCounter` immediately before each
  provider call.
- Share one outer budget across navigation and interpretation for the synchronization episode.
- Report actual calls in the synchronization result and attach a content-free recovery audit to the
  caller-scoped synchronization run. Schema v13 adds only bounded recovery metadata and structured
  event JSON to `booking_sync_runs`; it stores no provider content or Booking.com page evidence.

### Presentation and Failure Semantics

- Add recovery metadata to discovery/report domain values. Persist operator-facing recovery audit
  metadata as an additive schema-v13 extension to `booking_sync_runs`, preserving the existing
  caller lifecycle and purge path instead of overloading price-check traces.
- `/bookings` identifies assisted success or partial recovery.
- Failed refreshes display preserved reservations and clear retry or `/connect` guidance.
- Unexpected worker exceptions synthesize a caller-scoped failed completion, so an exception can
  never render as an empty Booking.com account.

## Trigger Coverage

All four triggers already enter `_synchronize_user`; wiring one fallback-capable source there
covers `/bookings`, post-`/connect`, `/checknow` prerequisite refresh, and scheduled refresh without
duplicating browser work or adding a queue.

## Security and Privacy

- Human login, credential entry, MFA, and viewer control remain outside the model.
- Sessions, cookies, API keys, raw HTML, and database state are never placed in recovery results.
- Provider/browser exceptions are category-normalized and durable traces omit page identifiers.
- A failed/incomplete assisted run retains ADR-028's no-absence mutation rule.

## ADR Analysis

No new ADR is required. ADR-030 already establishes the shared progress-aware recovery and
provider boundary; ADR-027 retains Booking.com account authority; ADR-028 retains conclusive
completeness and partial-run mutation rules. This bolt is a direct application of those decisions.

## Test Strategy

- Scripted healthy path with zero calls.
- Entry/readiness/navigation and redesigned scope-control recovery.
- Interpreter validation, provider failure, budget exhaustion, and caller accounting.
- Contradictory negative candidate preserving an existing eligible reservation.
- Completeness/absence safety on incomplete assisted runs.
- All synchronization triggers and unexpected `/bookings` worker failure UX.
- Full repository lint, type, test, CLI, artifact-integrity, and diff gates.
