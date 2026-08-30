---
id: ADR-041
title: Trigger-specific local Browser Use execution for bookings
status: accepted
created: 2026-08-30T18:15:00Z
bolt: 060-agentic-inventory-executor
---

# ADR-041: Trigger-Specific Local Browser Use Execution for `/bookings`

## Context

The local Stagehand inventory adapter has repeatedly reached infrastructure and provider-specific
failure modes before it could return useful inventory evidence. The control-plane boundary remains
sound, but Telegram `/bookings` needs a reliability-focused executor trial that does not put
scheduled checks, post-connect synchronization, `/checknow`, or price monitoring at simultaneous
risk.

Browser Use OSS provides an established full browser-agent loop with local browser control. Its
current `0.13.x` line hard-pins an Anthropic SDK version incompatible with BookSaver's qualified
runtime, while classic `0.11.13` declares a compatible Anthropic range and supports the required
local CDP/session and custom-tool APIs. Browser Use's default tools and popup handling are too broad
for an authenticated Booking.com session and cannot be accepted unchanged.

## Decision

Route only `SynchronizationTrigger.BOOKINGS` through a new local Browser Use OSS adapter behind the
existing `InventoryBrowserExecutor` port. Keep Stagehand for post-connect, `/checknow`, scheduled
inventory, and all currently assigned price work. A Browser Use terminal closes the `/bookings`
operation without same-job Stagehand or legacy fallback.

Pin Browser Use `0.11.13` exactly with its required settings dependency. Do not force incompatible
provider versions, use Browser Use Cloud, or adopt beta agent APIs. Requalification and a separate
decision are required before changing the pin or expanding trigger coverage.

Remove all stock browser actions and expose only BookSaver-owned guarded read-only click, scroll,
safe-key, wait, typed observation submission, and typed terminal submission. Require exact registry
equality at startup, one action per agent step, existing hard action/cost/deadline limits, and
per-physical-call cost admission/reconciliation. Disable Browser Use telemetry, cloud/version
checks, remote logs, history/media/trace persistence, and content exports before import.

Browser Use output remains untrusted evidence. BookSaver retains session custody, authentication
proof, fact validation, eligibility, positive-only reconciliation, persistence, and notification
authority. Interaction is deny-oriented and code-guarded before and after every action without
encoding exact benign labels, selectors, or route names. Replace stock popup automation with a
code-owned handler that dismisses all confirm/prompt dialogs and rejects unexpected tabs/popups.

## Rationale

- Trigger-specific routing makes the reliability experiment observable and reversible without a
  simultaneous migration of background or price work.
- Reusing the existing port and trusted validation boundary tests the executor, not BookSaver's
  accepted domain policies.
- The classic exact pin resolves normally alongside BookSaver's Anthropic SDK; an unsupported
  resolver override would undermine reliability.
- A closed custom tool registry and code-owned dialog behavior prevent harness defaults from gaining
  account-mutation authority.
- No same-job fallback prevents doubled budgets and exposes Browser Use failures honestly.

## Alternatives Considered

- **Replace Stagehand for every inventory trigger immediately**: rejected because it broadens blast
  radius before `/bookings` proves the adapter.
- **Upgrade to Browser Use `0.13.x` and override its Anthropic pin**: rejected because the resulting
  installation is outside upstream's declared compatibility contract.
- **Use Browser Use Cloud**: rejected because it adds a managed authenticated-browser boundary, new
  credentials, cost, and deployment dependency.
- **Keep Browser Use default tools**: rejected because navigation, typing, tab, file, and popup
  behaviors exceed BookSaver's read-only authority.
- **Fall back to Stagehand when Browser Use fails**: rejected because it masks qualification,
  duplicates browser work, and can exceed the containing operation's limits.

## Consequences

- Two local inventory adapters coexist temporarily and composition must remain trigger-specific.
- The exact Browser Use pin becomes a qualified runtime dependency and must be revisited deliberately
  as upstream's provider constraints change.
- `/bookings` may fail closed while other triggers continue through Stagehand; last-safe inventory
  remains available.
- Custom guard, model-accounting, dialog, and teardown integration require focused maintenance, but
  benign Booking.com DOM/label/route structure is no longer encoded as the execution strategy.
- Successful offline and container qualification still requires live Telegram acceptance because
  Booking.com's authenticated experience is dynamic.
