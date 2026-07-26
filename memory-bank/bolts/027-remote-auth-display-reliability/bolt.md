---
id: 027-remote-auth-display-reliability
unit: 001-remote-auth-display-reliability
intent: 014-remote-auth-display-reliability
type: simple-construction-bolt
status: complete
stories:
  - 001-render-remote-browser-framebuffer
  - 002-explain-viewer-connection-failures
created: 2026-07-26T17:55:43.000Z
started: 2026-07-26T17:57:48.000Z
completed: "2026-07-26T18:12:47Z"
current_stage: null
stages_completed:
  - name: plan
    completed: 2026-07-26T18:09:55.000Z
    artifact: implementation-plan.md
  - name: implement
    completed: 2026-07-26T18:11:07.000Z
    artifact: implementation-walkthrough.md
  - name: test
    completed: 2026-07-26T18:12:24.000Z
    artifact: test-walkthrough.md
requires_bolts:
  - 026-remote-authentication-gateway
enables_bolts: []
requires_units: []
blocks: false
complexity:
  avg_complexity: 1
  avg_uncertainty: 1
  max_dependencies: 2
  testing_scope: 3
---

# Bolt: 027-remote-auth-display-reliability

## Objective

Correct the production Telegram `/connect` gray screen by allowing only noVNC's required inline
image decoding and by surfacing safe viewer failures, with automated regression coverage.

## Stories Included

- **001-render-remote-browser-framebuffer**: Render the remote mobile-browser framebuffer (Must)
- **002-explain-viewer-connection-failures**: Explain remote viewer connection failures (Must)

## Bolt Type

**Type**: Simple Construction Bolt
**Definition**: `.specsmd/aidlc/templates/construction/bolt-types/simple-construction-bolt.md`

## Stages

- [x] **1. Plan**: Complete → `implementation-plan.md`
- [x] **2. Implement**: Complete → source and tests
- [x] **3. Test**: Complete → `test-walkthrough.md`

## Dependencies

### Requires

- Bolt 026 remote-authentication gateway (Complete).

### Enables

- Production `/connect` acceptance testing.

## Success Criteria

- [x] Both stories implemented and acceptance criteria met.
- [x] CSP remains deny-by-default and permits only required data images.
- [x] Viewer failures produce safe, actionable status text.
- [x] Targeted and full tests, Ruff, mypy, and diff checks pass.
- [x] Human review occurs before Git or deployment actions.

## Execution Authorization

The product owner explicitly requested the diagnosed fix and AI-DLC documentation. Construction
through Test is authorized; commit, push, merge, and deployment remain held for final approval.
