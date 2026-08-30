---
id: 061-agentic-inventory-executor
unit: 004-agentic-inventory-executor
intent: 023-replaceable-agentic-browser-executor
type: ddd-construction-bolt
status: in-progress
stories:
  - 007-enter-browser-use-inventory-through-canonical-https
created: 2026-08-30T22:28:13Z
started: 2026-08-30T22:28:13Z
completed: null
current_stage: test
stages_completed:
  - name: domain-model
    completed: 2026-08-30T22:29:00Z
    artifact: ddd-01-domain-model.md
  - name: technical-design
    completed: 2026-08-30T22:30:00Z
    artifact: ddd-02-technical-design.md
  - name: adr-analysis
    completed: 2026-08-30T22:30:30Z
    artifact: none-required-existing-adr-041
  - name: implement
    completed: 2026-08-30T22:39:48Z
    artifact: source-and-regression-tests
requires_bolts:
  - 060-agentic-inventory-executor
enables_bolts: []
requires_units:
  - 001-agentic-executor-control-plane
  - 002-local-agentic-price-executor
blocks: false
complexity:
  avg_complexity: 1
  avg_uncertainty: 1
  max_dependencies: 2
  testing_scope: 3
---

# Bolt: Canonical HTTPS Browser Use Inventory Entry

## Objective

Replace only Browser Use's obsolete inventory entry with Booking.com's canonical HTTPS `mytrips`
route so `/bookings` reaches perception without permitting the observed HTTP redirect.

## Stories Included

- [ ] **US-161**: Enter Browser Use inventory through canonical HTTPS - Priority: Must

## Expected Outputs

- Browser Use-specific code-owned HTTPS inventory entry.
- Guarded same-tab replay for safe read-only links that would otherwise create a popup.
- Interactive-ancestor guarding that ignores unrelated structural aggregate text.
- Bounded recovery from a rejected pre-action proposal with content-free reason diagnostics.
- Regression coverage for direct entry and continued HTTP denial.
- Bounded authenticated VPS replay proving inventory discovery.

## Dependencies

- Bolt 060 and ADR-041 are complete and binding.

## Success Criteria

- [ ] Direct HTTPS inventory navigation reaches a Booking.com page.
- [ ] HTTP egress remains denied.
- [ ] Safe read-only `target=_blank` links cannot create tabs and retain destination checks.
- [ ] Structural aggregate text cannot reject a valid interactive link; app-install and mutation
  controls remain blocked before replay.
- [ ] A rejected proposal consumes the action allowance and permits a bounded retry.
- [ ] Browser Use advances into agent perception and returns validated positive inventory.
- [ ] Other inventory triggers, safety boundaries, and execution caps remain unchanged.
