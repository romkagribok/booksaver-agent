---
id: 076-price-terminal-contract
unit: 011-grouped-trip-discovery
intent: 023-replaceable-agentic-browser-executor
type: ddd-construction-bolt
status: complete
stories:
  - 005-close-price-terminal-contract
created: "2026-09-14T20:01:15Z"
started: "2026-09-14T20:01:15Z"
completed: "2026-09-14T20:22:49Z"
current_stage: null
stages_completed:
  - name: domain-model
    completed: "2026-09-14T20:01:15Z"
    artifact: ddd-01-domain-model.md
  - name: technical-design
    completed: "2026-09-14T20:01:15Z"
    artifact: ddd-02-technical-design.md
  - name: adr-analysis
    completed: "2026-09-14T20:01:15Z"
    artifact: ddd-02-technical-design.md
  - name: implement
    completed: "2026-09-14T20:22:49Z"
    artifact: source-and-tests
  - name: test
    completed: "2026-09-14T20:22:49Z"
    artifact: ddd-03-test-report.md
requires_bolts:
  - 075-grouped-discovery-review-edges
enables_bolts: []
requires_units: []
blocks: false
complexity:
  avg_complexity: 2
  avg_uncertainty: 1
  max_dependencies: 1
  testing_scope: 2
---

# Price submission contract and interrupted-run diagnosis

Image B passed inventory and AIRINN but Park Inn repeated a 179-second timeout with 13 model
calls and only 3 actions. Production remains PR50; PR51 has not merged. This returns Unit011
to Construction under the user's explicit iterative fix, verification, merge/deploy authority.
The terminal schema defect is independently established; its causal connection to Park Inn is
not yet claimed. No release, review, safety or pricing criterion is waived.

A later unchanged-image sequential replay exposed repeated incomplete observation submissions,
then complete success without further browser actions (130.205 seconds, 8 calls, 4 actions).
Scope therefore also clarifies query-versus-offer completeness, matching existing domain filtering.
No cross-job state leak is claimed; schema/screenshot isolation checks did not reproduce one.
