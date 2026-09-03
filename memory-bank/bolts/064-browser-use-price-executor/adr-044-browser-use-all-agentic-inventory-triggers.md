---
id: ADR-044
title: Browser Use for all agentic inventory triggers
status: accepted
created: 2026-09-03T00:36:00Z
bolt: 064-browser-use-price-executor
---

# ADR-044: Browser Use for All Agentic Inventory Triggers

## Context

The first exact-container price replay entered the real `/checknow` coordinator and terminated as
unavailable before constructing the new price executor. Production composition still routed the
required current-run inventory verification through Stagehand, while only `/bookings` used the
proven Browser Use inventory adapter. This preserved the failure dependency the price migration was
intended to remove and made Browser Use price execution unreachable when Stagehand inventory failed.

## Decision

Use the existing pinned, guarded local Browser Use inventory adapter for every agentic inventory
trigger in production composition: `/bookings`, `/checknow`, scheduled, and post-connect. Preserve
the same provider-neutral inventory port, current-run positive-only reconciliation, disclosure,
session custody, guards, limits, and one-inventory-run-per-operation rule.

Keep `inventory_routing = "legacy"` as the explicit future-job rollback. Do not cascade from Browser
Use to Stagehand or legacy inside a failed operation. This decision supersedes ADR-041's temporary
trigger-specific rollout restriction; its safety and confinement decisions remain binding.

## Consequences

- Browser Use price execution is no longer gated by Stagehand inventory availability.
- Scheduled and post-connect inventory now use the same already-live Browser Use adapter as
  `/bookings`, increasing its trigger coverage but not its browser authority.
- Inventory and price still consume one shared outer job budget and deadline.
- A Browser Use inventory terminal remains visible and fail-closed; it cannot be masked by another
  harness in the same operation.

## Validation

- Production-composition test asserting both inventory factory slots construct Browser Use.
- Existing trigger, positive-evidence, authorization, safety, privacy, budget, and reconciliation
  suites.
- Exact-container VPS replay through the real `/checknow` coordinator.
