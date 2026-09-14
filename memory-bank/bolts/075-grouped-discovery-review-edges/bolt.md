---
id: 075-grouped-discovery-review-edges
unit: 011-grouped-trip-discovery
intent: 023-replaceable-agentic-browser-executor
type: ddd-construction-bolt
status: complete
stories:
  - 004-close-grouped-discovery-review-edges
created: "2026-09-14T19:34:14Z"
started: "2026-09-14T19:34:14Z"
completed: "2026-09-14T19:41:31Z"
current_stage: null
stages_completed:
  - name: domain-model
    completed: "2026-09-14T19:34:14Z"
    artifact: ddd-01-domain-model.md
  - name: technical-design
    completed: "2026-09-14T19:34:14Z"
    artifact: ddd-02-technical-design.md
  - name: adr-analysis
    completed: "2026-09-14T19:34:14Z"
    artifact: ddd-02-technical-design.md
  - name: implement
    completed: "2026-09-14T19:40:42Z"
    artifact: source-and-tests
  - name: test
    completed: "2026-09-14T19:40:42Z"
    artifact: ddd-03-test-report.md
requires_bolts:
  - 074-grouped-trip-discovery
enables_bolts: []
requires_units: []
blocks: false
complexity:
  avg_complexity: 2
  avg_uncertainty: 1
  max_dependencies: 1
  testing_scope: 2
---

# Bolt 075: Grouped Discovery Review Edges

PR51 review found late-card readiness and inactive-only grouped outcomes after Bolt074's local
and caller acceptance. Preserve Bolt074's completed historical evidence; this follow-up returns
Unit011 from Operations to construction for the two scoped review corrections. The user's
explicit iterative fix/merge/deploy authorization covers this checkpoint. No release gate is
waived; the replacement image must be qualified before promotion.

Both review corrections passed the final construction gate: 2,609 tests, 83% coverage, Ruff,
mypy, and AI-DLC checks. Construction acceptance does not qualify the initial image for promotion;
its second staged price check timed out. Final-head review and replacement-image verification
remain required in Operations.
