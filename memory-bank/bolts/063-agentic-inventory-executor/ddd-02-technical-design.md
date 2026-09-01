---
stage: design
bolt: 063-agentic-inventory-executor
created: 2026-09-01T01:12:00Z
---

# Technical Design: Positive-Only Inventory Outcome

## Domain Boundary

Add a read-only `SynchronizationReport.accepted_positive_observations` predicate. It is true only
when scope is intentionally incomplete, no failure code exists, and at least one observation was
accepted. Keep `succeeded` unchanged so authoritative completeness remains explicit.

## Presentation Boundary

Telegram checks `succeeded` first, then `accepted_positive_observations`. The positive-only branch
states that current observations were refreshed and unseen saved reservations were preserved. The
existing incomplete branch remains for rejected or ambiguous partial evidence.

## Verification

- Domain tests prove the predicates are mutually meaningful and failure codes prevent positive
  acceptance.
- Telegram tests prove the safe success wording and retain the ambiguous incomplete warning.
- The VPS probe instantiates the real coordinator, waits for callback completion, and maps either
  authoritative completeness or accepted positive observations to exit zero.

## ADR Analysis

No new ADR is required. ADR-039 already requires positive-only agentic inventory and forbids
model-declared absence; this bolt corrects presentation and acceptance semantics without changing
browser, persistence, or reconciliation authority.
