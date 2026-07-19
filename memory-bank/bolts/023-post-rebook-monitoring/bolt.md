---
id: 023-post-rebook-monitoring
unit: 001-post-rebook-monitoring
intent: 011-post-rebook-monitoring
type: ddd-construction-bolt
status: complete
stories:
  - 001-collect-actual-replacement-facts
  - 002-propagate-monitored-replacement-atomically
  - 003-reconcile-partial-outcomes-safely
  - 004-preserve-audit-and-invalidate-stale-savings
  - 005-preserve-access-and-visible-completion
created: 2026-07-19T19:50:29.000Z
started: 2026-07-19T19:53:22.000Z
completed: "2026-07-19T20:23:12Z"
current_stage: null
stages_completed:
  - name: model
    completed: 2026-07-19T19:54:15.000Z
    artifact: ddd-01-domain-model.md
  - name: design
    completed: 2026-07-19T19:55:13.000Z
    artifact: ddd-02-technical-design.md
  - name: adr-analysis
    completed: 2026-07-19T19:55:13.000Z
    artifact: adr-023-stable-id-post-rebook-propagation.md
  - name: implement
    completed: 2026-07-19T20:04:58.000Z
    artifact: domain/post_rebook.py + application/post_rebook.py + PostRebookRepository + SqliteBookingRepository reconciliation + Telegram rebook_propagation/gateway wiring
  - name: test
    completed: 2026-07-19T20:06:55.000Z
    artifact: ddd-03-test-report.md
requires_bolts:
  - 011-telegram-rebook-gate
  - 017-conversational-booking-management
  - 022-telegram-privacy-boundaries
enables_bolts: []
requires_units:
  - 004-telegram-rebook-gate
  - 001-conversational-booking-management
  - 001-telegram-privacy-boundaries
blocks: false
complexity:
  avg_complexity: 3
  avg_uncertainty: 2
  max_dependencies: 3
  testing_scope: 3
---

# Bolt: 023-post-rebook-monitoring

## Objective

Close the Telegram device-handoff lifecycle by reconciling actual outcomes, collecting actual checkout
facts, and atomically continuing monitoring from the replacement reservation when safe.

## Stories Included

- [x] **US-072**: Collect actual replacement facts - Must.
- [x] **US-073**: Propagate monitored replacement atomically - Must.
- [x] **US-074**: Reconcile partial outcomes safely - Must.
- [x] **US-075**: Preserve audit and invalidate stale savings - Must.
- [x] **US-076**: Preserve access and visible completion - Must.

## Expected Outputs

- Domain outcome/propagation model and technical design.
- Telegram actual-facts dialog integrated with rebook outcome follow-up.
- Application repository contract and atomic SQLite reconciliation.
- Outcome, persistence, concurrency, ownership, revocation, and regression tests.

## Dependencies

- Bolt 011 and ADR-012 for the device handoff and audit trail.
- Bolt 017 for stable aggregate mutation and stale-savings behavior.
- Bolt 022 for private-chat, ownership, and revocation barriers.

## Success Criteria

- [x] No detected offer price is silently treated as paid.
- [x] Every partial outcome has one safe monitoring disposition.
- [x] Replacement/archive transitions are atomic and audit-preserving.
- [x] Future checks use the actual replacement baseline.
- [x] Focused and full quality gates pass.

## Execution Authorization

The product owner authorized continuous execution through the final Test checkpoint. Formal bolt
completion, commit, push, merge, and deployment remain held for main-agent review.
