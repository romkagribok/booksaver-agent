---
id: 001-prove-jev-price-feasibility
unit: 001-jev-price-executor
intent: 026-jev-price-comparison
status: draft
priority: must
created: "2026-09-26T16:33:08Z"
assigned_bolt: 084-jev-price-executor
implemented: false
---

# US-204: Prove Jev price feasibility

## User story

As a operator, I want to know whether a complete Jev-only price path is viable before production integration, so the price comparison is trustworthy and actionable.

## Assigned requirement

FR-1; shared NFRs in ../../../requirements.md. The complete pair contract is in
../../../experiment-design.md.

## Acceptance criteria

- [ ] Given sanitized representative Booking.com fixtures, when the spike runs, then it demonstrates navigation and evidence extraction sufficient for the unchanged validator, or records the exact unsupported cases and a blocked conclusion.
- [ ] Given the upstream Jev project, when choosing reuse, then record reviewed source revision/license, dependency implications and compatibility with local session/guard/budget contracts; no stock personal-profile runtime is adopted.
- [ ] Given supported and adversarial cases, when selecting the implementation, then provide an executable local proof with no non-Jev helper; offline fake decisions prove plumbing only and are labelled separately from live model quality.
- [ ] Given deadline/call/action requirements, when the spike exits, then propose finite candidate limits and observation bounds with representative evidence for construction design.

## Technical notes

Run isolated local pages first; paid external/model qualification waits for actual credentials and admitted budget.

## Dependencies

Requires: None (first feasibility story).
Assigned bolt: 084-jev-price-executor. Downstream dependencies are recorded in units.md and bolt frontmatter.

## Edge cases

Missing/ambiguous evidence is an explicit terminal, never guessed success. Interrupted or denied work
retains cost and method attribution. Recheck user/session authority at execution and delivery.

## Out of scope

Inventory conversion, Stagehand removal, autonomous booking actions, provider/payer fallback and
claims of qualification without evidence.
