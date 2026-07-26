---
intent: 014-remote-auth-display-reliability
phase: inception
status: units-decomposed
updated: 2026-07-26T17:55:43Z
---

# Remote Authentication Display Reliability - Unit Decomposition

## Units Overview

This defect fix decomposes into one cohesive unit.

### Unit 1: `001-remote-auth-display-reliability`

**Description**: Correct the Mini App viewer policy and add safe noVNC failure feedback.

**Assigned Requirements**: FR-1, FR-2.

**Deliverables**:

- Narrow CSP correction.
- RFB failure/disconnect status handling.
- Regression tests and construction evidence.

**Dependencies**:

- Existing Intent 012 remote-authentication gateway.
- Packaged noVNC, x11vnc, websockify, Caddy, and Telegram Mini App identity exchange.

**Estimated Complexity**: Small implementation, medium production/security risk.

## Requirement-to-Unit Mapping

- **FR-1**: Render noVNC framebuffer image updates → `001-remote-auth-display-reliability`
- **FR-2**: Explain noVNC connection failures → `001-remote-auth-display-reliability`

## Execution Order

`001-remote-auth-display-reliability` executes as Bolt 027 after the completed remote-auth gateway.
