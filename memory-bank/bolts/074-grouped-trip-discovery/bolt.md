---
id: 074-grouped-trip-discovery
unit: 011-grouped-trip-discovery
intent: 023-replaceable-agentic-browser-executor
type: ddd-construction-bolt
status: complete
stories:
  - 001-discover-grouped-reservations-and-details
  - 002-preserve-eligibility-and-distinguish-current-stays
  - 003-qualify-grouped-discovery-and-final-image
created: "2026-09-13T16:10:04Z"
started: "2026-09-13T16:11:46Z"
completed: "2026-09-14T19:23:37Z"
current_stage: null
stages_completed:
  - name: domain-model
    completed: "2026-09-13T16:11:46Z"
    artifact: ddd-01-domain-model.md
  - name: technical-design
    completed: "2026-09-13T16:12:37Z"
    artifact: ddd-02-technical-design.md
  - name: adr-analysis
    completed: "2026-09-13T16:12:37Z"
    artifact: ddd-02-technical-design.md
  - name: implement
    completed: "2026-09-14T19:23:09Z"
    artifact: source-and-tests
  - name: test
    completed: "2026-09-14T19:23:09Z"
    artifact: ddd-03-test-report.md
requires_bolts:
  - 063-agentic-inventory-executor
  - 065-shared-browser-use-access
  - 073-caller-inventory-outcomes
enables_bolts: []
requires_units: []
blocks: false
complexity:
  avg_complexity: 2
  avg_uncertainty: 2
  max_dependencies: 2
  testing_scope: 3
---

# Bolt 074: Grouped Trip Discovery

## Objective and scope

Discover and audit grouped trips, reservation identities, and required details; keep incomplete
facts ineligible and current/upcoming status accurate; qualify the real caller and exact final
image through the authorized release workflow. US-187 through US-189 are all Must.

## Construction entry

Domain model, technical design, and existing-ADR analysis are documented. Construction starts with
the confirmed explicit lifecycle-fact correction and bounded code-owned worklist contract. Concrete
grouped-page extraction/navigation details remain assumptions awaiting fresh authenticated evidence;
no live coverage or eligibility claim is made. Positive-only reconciliation prevents destructive
absence updates even if all reachable views have been examined.

The user authorized the end-to-end AI-DLC correction, verification loop, merge, and redeployment.
Routine checkpoints are covered by that approval; security/product scope changes and final-head
Bugbot/exact-image verification remain substantive gates. Main agent owns final evidence and release.

## Expected outputs

Domain model, evidence-grounded technical design, any justified ADR, bounded implementation,
deterministic coverage/eligibility fixtures, actual-caller isolated acceptance, quality/review gate,
and operations evidence for the exact promoted image. Preserve prior Bolt 073 records as history.
