---
id: 056-agentic-inventory-executor
unit: 004-agentic-inventory-executor
intent: 023-replaceable-agentic-browser-executor
type: ddd-construction-bolt
status: complete
stories:
  - 002-tolerate-read-only-destinations-and-diagnose-rejections
created: 2026-08-27T23:13:41.000Z
started: 2026-08-27T23:13:41.000Z
completed: "2026-08-27T23:26:26Z"
current_stage: null
stages_completed:
  - name: domain-model
    completed: 2026-08-27T23:16:47.000Z
    artifact: ddd-01-domain-model.md
  - name: technical-design
    completed: 2026-08-27T23:17:21.000Z
    artifact: ddd-02-technical-design.md
  - name: adr-analysis
    completed: 2026-08-27T23:17:45.000Z
    artifact: adr-040-separate-observation-from-interaction-authority.md
  - name: implement
    completed: 2026-08-27T23:22:35.000Z
    artifact: ../../src/booksaver/infrastructure/browser/agentic_inventory_executor.py
  - name: test
    completed: 2026-08-27T23:26:06.000Z
    artifact: ddd-03-test-report.md
requires_bolts:
  - 053-agentic-inventory-executor
enables_bolts: []
requires_units:
  - 001-agentic-executor-control-plane
  - 002-local-agentic-price-executor
blocks: false
complexity:
  avg_complexity: 2
  avg_uncertainty: 2
  max_dependencies: 3
  testing_scope: 3
---

# Bolt: Agentic Inventory Destination Policy

## Objective

Replace brittle exact inventory path/query admission with layered Booking.com observation and
interaction policy, and make destination failures locally diagnosable without retaining sensitive
URLs or page content.

## Stories Included

- [x] **US-156**: Tolerate read-only destinations and diagnose rejections - Priority: Must

## Expected Outputs

- Three-level destination disposition for Booking.com inventory navigation.
- Sanitized, bounded rejection diagnostics in local logs.
- Regression coverage for benign redirect/query churn and prohibited destination families.
- No change to domain egress, mutation guards, session custody, or positive-only reconciliation.

## Dependencies

- Bolt 053 and ADR-034, ADR-036, ADR-037, and ADR-039 are complete and binding.

## Success Criteria

- [x] Benign Booking.com route/query churn can reach semantic extraction without a code update.
- [x] Unknown Booking.com pages cannot gain interaction authority merely by being observable.
- [x] Known sensitive or mutating destinations remain blocked before model-controlled interaction.
- [x] Logs identify rejection class and sanitized route shape without raw URL or account data.
- [x] Focused security tests and the full repository quality gate pass.
