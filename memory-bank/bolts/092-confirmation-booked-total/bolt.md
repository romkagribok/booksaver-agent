---
id: 092-confirmation-booked-total
unit: 013-confirmation-booked-total
intent: 023-replaceable-agentic-browser-executor
type: ddd-construction-bolt
status: complete
stories:
  - 001-record-confirmation-total-in-printed-currency
  - 002-replace-saved-total-with-page-verified-total
  - 003-qualify-confirmation-total-for-affected-caller
created: "2026-10-10T01:59:26Z"
started: "2026-10-10T02:00:18Z"
completed: "2026-10-12T22:18:02Z"
current_stage: null
stages_completed:
  - name: domain-model
    completed: "2026-10-10T02:00:33Z"
    artifact: ddd-01-domain-model.md
  - name: technical-design
    completed: "2026-10-10T02:01:25Z"
    artifact: ddd-02-technical-design.md
  - name: adr-analysis
    completed: "2026-10-10T02:01:25Z"
    artifact: adr-058-page-verified-booked-total.md
  - name: implement
    completed: "2026-10-10T02:04:30Z"
    artifact: src/booksaver/infrastructure/browser/inventory_confirmation_facts.py
  - name: test
    completed: "2026-10-12T22:18:02Z"
    artifact: ddd-03-test-report.md
requires_bolts:
  - 077-trusted-inventory-reconciliation
enables_bolts: []
requires_units: []
blocks: false
complexity:
  avg_complexity: 2
  avg_uncertainty: 3
  max_dependencies: 2
  testing_scope: 3
---

# 092-confirmation-booked-total

## Objective

Make a refresh record the confirmation page's booked total in its printed currency and let that
page-verified total replace a stale saved baseline.

## Stories included

- [ ] US-226: Record the confirmation total in its printed currency (Must)
- [ ] US-227: Replace a stale saved total with the page-verified total (Must)
- [ ] US-228: Qualify the confirmation total for the affected caller (Must)

## Stages and expected outputs

- [x] Domain model: ddd-01-domain-model.md.
- [x] Technical design: ddd-02-technical-design.md.
- [x] ADR analysis: ADR-058 accepted; it amends ADR-048's saved-total rule.
- [x] Implement: scoped source and tests; no schema migration.
- [x] Test: ddd-03-test-report.md records the automated results and the affected-caller replay.

Definition: .specsmd/aidlc/templates/construction/bolt-types/ddd-construction-bolt.md.

## Scope and qualification notes

The owner waived per-step approval for this task and required every step to be recorded.
The dollar layout is known only from a cropped screenshot of the owner's confirmation page; the
lines below its "Price" row are assumed to match the euro layout. Affected-caller replay is
therefore part of acceptance and needs separate approval because it touches the production host.

## Status at 2026-10-10T02:05:01Z

Domain model, technical design, ADR-058 and implementation are recorded. Automated verification
passed (3,125 tests, Ruff, mypy 131 modules, 16 validator tests). The bolt stays in progress at
the test stage: US-228 requires an isolated replay against the affected caller's real confirmation
page, which has not been run and needs separate owner approval. The completion cascade has not
been run. Nothing is committed, merged or deployed.

## Status at 2026-10-12T22:18:02Z

Rebased onto main 108bc23 and renumbered from provisional 089/US-216–218/ADR-056. The
affected-caller replay passed on the real confirmation page after the reader was corrected to the
observed layout (see the design amendment and test report). All three stories' criteria are met.
Construction is complete; nothing is committed, merged or deployed, and Operations has not begun.
