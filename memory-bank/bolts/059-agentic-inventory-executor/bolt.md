---
id: 059-agentic-inventory-executor
unit: 004-agentic-inventory-executor
intent: 023-replaceable-agentic-browser-executor
type: ddd-construction-bolt
status: in-progress
stories:
  - 005-preserve-mobile-session-identity-and-classify-navigation-failure
created: 2026-08-29T20:51:44Z
started: 2026-08-29T20:51:44Z
completed: null
current_stage: test
stages_completed:
  - name: domain-model
    completed: 2026-08-29T21:02:00Z
    artifact: ddd-01-domain-model.md
  - name: technical-design
    completed: 2026-08-29T21:07:00Z
    artifact: ddd-02-technical-design.md
  - name: adr-analysis
    completed: 2026-08-29T21:08:00Z
    artifact: none-required-existing-adrs-024-025-026-036-037-038-039-040
  - name: implement
    completed: 2026-08-29T21:22:00Z
    artifact: source-and-regression-tests
requires_bolts:
  - 053-agentic-inventory-executor
  - 056-agentic-inventory-executor
  - 057-agentic-inventory-executor
  - 058-agentic-inventory-executor
enables_bolts: []
requires_units:
  - 001-agentic-executor-control-plane
  - 002-local-agentic-price-executor
blocks: false
complexity:
  avg_complexity: 2
  avg_uncertainty: 1
  max_dependencies: 2
  testing_scope: 3
---

# Bolt: Mobile Session Identity and Navigation Failure

## Objective

Make authenticated Stagehand execution use BookSaver's accepted version-matched mobile identity and
surface browser transport/authentication failures before semantic or computer-use work.

## Stories Included

- [ ] **US-159**: Preserve mobile session identity and classify navigation failure - Priority: Must

## Expected Outputs

- Mobile-profile injection into both local agentic executor factories.
- Version-matched Stagehand launch identity without exposing it to the model.
- Closed, sanitized navigation-failure classification and inventory terminal mapping.
- Regression coverage for desktop OAuth loop, mobile success, zero-model-call failure, and privacy.
- AI-DLC construction artifacts, exact-image smoke, and production deployment evidence.

## Dependencies

- Bolts 053, 056, 057, and 058 are complete.
- ADR-024 through ADR-026 and ADR-036 through ADR-040 remain binding.

## Success Criteria

- [ ] The production `ERR_TOO_MANY_REDIRECTS` reproduction succeeds under the configured Pixel 7
  Stagehand identity.
- [ ] Browser transport failures are typed before destination guarding or provider inference.
- [ ] Session custody, action safety, positive-only reconciliation, cost, and privacy boundaries are
  unchanged.
- [ ] Focused, repository-wide, AI-DLC, Bugbot, exact-image, and production gates pass.
