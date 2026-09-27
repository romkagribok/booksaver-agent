---
id: 003-guard-jev-browser-decisions
unit: 001-jev-price-executor
intent: 026-jev-price-comparison
status: draft
priority: must
created: "2026-09-26T16:33:08Z"
assigned_bolt: 085-jev-price-executor
implemented: false
---

# US-206: Guard Jev browser decisions

## User story

As a user, I want to allow Jev to choose only current permitted browser actions, so the price comparison is trustworthy and actionable.

## Assigned requirement

FR-4; shared NFRs in ../../../requirements.md. The complete pair contract is in
../../../experiment-design.md.

## Acceptance criteria

- [ ] Given a visible page, when observing, then produce bounded relevant controls with observation-scoped references and compatible operation/target sets including blocked/unknown.
- [ ] Given stale, hidden, occluded, detached or prohibited controls, when a selection is executed, then reject/reobserve within limits and never dispatch an unsafe action.
- [ ] Given injected page instructions or contradictory operation/target heads, when the decision is received, then code-owned authority and compatibility guards still reject invalid actions.
- [ ] Given a fill action, when it executes, then its value is bound to a trusted field/value from the request or an observed permitted option, never arbitrary model text.
- [ ] Given no progress, no supported controls or low confidence, when limits/threshold policy applies, then emit a bounded terminal and do not delegate to Anthropic or generated JS.

## Technical notes

Reuse existing browser/session/guard primitives where qualified; account for frames/widgets unsupported by the reference project.

## Dependencies

Requires: US-204, US-205.
Assigned bolt: 085-jev-price-executor. Downstream dependencies are recorded in units.md and bolt frontmatter.

## Edge cases

Missing/ambiguous evidence is an explicit terminal, never guessed success. Interrupted or denied work
retains cost and method attribution. Recheck user/session authority at execution and delivery.

## Out of scope

Inventory conversion, Stagehand removal, autonomous booking actions, provider/payer fallback and
claims of qualification without evidence.
