---
unit: 012-trusted-inventory-reconciliation
intent: 023-replaceable-agentic-browser-executor
status: in-progress
default_bolt_type: ddd-construction-bolt
created: 2026-09-19T22:04:01Z
---

# Trusted Inventory Reconciliation

## Scope and requirements

FR-31 / US-192: Establish trusted current-list coverage and retire saved active reservations absent
from that proven scope. FR-32 / US-193: Keep cancellation/rebooking identities distinct and make
preserved, unverified saved records explicit. FR-33 / US-194: Verify authority, persistence and
caller-visible behavior through fixtures, affected-caller replay and the release gates.

The user explicitly approved the AI-DLC follow-up through implementation, verification, merge and
deployment, including scoped checkpoints. The change is local inventory reconciliation; it never
cancels or changes a Booking.com reservation. Preserve the prior Unit011 release as historical work.

## Domain and boundaries

A trusted active-inventory proof is separate from model claims and diagnostic traversal counts.
It binds caller, run, session revision and recognized scope to positively established exhaustion,
resolved identities and stable membership. Unsupported or incomplete views remain positive-only.
Retirement removes a missing active row from current/monitoring projections while preserving its
history; it does not assert cancellation. Exact confirmed cancellation is a separate positive fact.
Rebooking creates a distinct confirmation identity even when hotel/dates are unchanged.

Use the existing coordinator/browser lease, safety and budget limits, SQLite transaction, current-run
price receipt and caller-scoped presentation boundaries. No new service, browser route or dependency.
Dependencies: completed Units004,010,011; existing current-list synchronization and eligibility policy.

## Story summary

Three Must stories, US192–194, assigned only to Bolt077. Construction is in progress. The domain
model, technical proof contract and ADR049 are accepted; implementation is in progress.
No runtime completion, live acceptance, merge or deployment is claimed by this setup.

## Exit criteria

Construction requires implemented stories, meaningful negative and positive regressions, quality
and AI-DLC gates, documented actual-caller acceptance, and the official bolt-complete cascade.
Operations separately requires successful current-head Bugbot and merge gate, exact-image Dev and
isolated Staging, restricted backup/rollback, authorized promotion and production health/state checks.
Native Telegram interaction and isolated replay are distinct evidence; do not substitute one for another.
