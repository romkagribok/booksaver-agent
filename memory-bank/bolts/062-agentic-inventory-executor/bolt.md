---
id: 062-agentic-inventory-executor
unit: 004-agentic-inventory-executor
intent: 023-replaceable-agentic-browser-executor
type: ddd-construction-bolt
status: complete
stories:
  - 008-discover-previously-unknown-browser-use-inventory
created: 2026-08-31T21:57:00Z
started: 2026-08-31T21:57:00Z
completed: 2026-08-31T23:33:00Z
current_stage: null
stages_completed:
  - name: domain-model
    completed: 2026-08-31T21:58:00Z
    artifact: ddd-01-domain-model.md
  - name: technical-design
    completed: 2026-08-31T21:59:00Z
    artifact: ddd-02-technical-design.md
  - name: adr-analysis
    completed: 2026-08-31T22:00:00Z
    artifact: adr-042-booking-waf-token-bootstrap-egress.md
  - name: implement
    completed: 2026-08-31T23:24:00Z
    artifact: source-and-regression-tests
  - name: test
    completed: 2026-08-31T23:33:00Z
    artifact: full-quality-gate-and-exact-image-empty-repository-proof
requires_bolts:
  - 061-agentic-inventory-executor
enables_bolts: []
requires_units:
  - 001-agentic-executor-control-plane
  - 002-local-agentic-price-executor
blocks: false
complexity:
  avg_complexity: 2
  avg_uncertainty: 2
  max_dependencies: 2
  testing_scope: 3
---

# Bolt: Genuine Browser Use Inventory Discovery

## Objective

Remove the cached-row completion shortcut, retain stable identity separately from optional facts,
and prove that `/bookings` can discover a current Booking.com reservation that is absent from the
caller-owned repository.

## Stories Included

- [x] **US-162**: Discover previously unknown Browser Use inventory - Priority: Must

## Expected Outputs

- No saved-stay early return before Browser Use execution.
- Strict provider-compatible identity and optional-fact submissions.
- Bounded visible-upcoming enumeration task and content-free diagnostics.
- Unit, integration, container, and isolated authenticated VPS discovery proof.

## Dependencies

- Bolt 061 and ADR-039 through ADR-042 are complete and binding.

## Success Criteria

- [x] A known visible stay does not suppress the Browser Use agent.
- [x] Unknown visible confirmation identity is accepted and optional facts merge independently.
- [x] Existing safety, privacy, budget, deadline, teardown, and positive-only boundaries pass.
- [x] An isolated empty-repository VPS replay discovers the real visible upcoming reservation.
