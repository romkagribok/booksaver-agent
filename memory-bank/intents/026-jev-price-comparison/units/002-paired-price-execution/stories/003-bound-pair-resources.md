---
id: 003-bound-pair-resources
unit: 002-paired-price-execution
intent: 026-jev-price-comparison
status: draft
priority: must
created: "2026-09-26T16:33:08Z"
assigned_bolt: 086-paired-price-execution
implemented: false
---

# US-211: Bound pair resources

## User story

As a owner, I want to run both methods without uncontrolled spend or scheduler starvation, so the price comparison is trustworthy and actionable.

## Assigned requirement

FR-8; shared NFRs in ../../../requirements.md. The complete pair contract is in
../../../experiment-design.md.

## Acceptance criteria

- [ ] Given a logical pair, when admitted, then it consumes one check allowance but every call/charge consumes governed usage; per-arm envelopes and hard aggregate caps are explicit.
- [ ] Given either arm runs first, when spending occurs, then it cannot consume reserved sibling capacity; denied admission is stored as not-run with reason.
- [ ] Given inventory plus multiple bookings and paired deadlines, when executing, then residual parent limits are never reset per booking or arm; 180s arm/360s pair/proposed 540s combined maxima are enforced only in explicit paired mode.
- [ ] Given shutdown, exhausted global cap, deadline crossing or cleanup failure, when another phase would start, then stop and terminalize it with no new browser.
- [ ] Given representative scheduled load, when pairing doubles potential browser work, then measure busy rejection/missed-slot behavior and verify baseline-only mode restores original bounds.

## Technical notes

Document ADR amendment for paired time scope; record shared inventory costs once; deployment caps must be finite before activation.

## Dependencies

Requires: US-208, US-209.
Assigned bolt: 086-paired-price-execution. Downstream dependencies are recorded in units.md and bolt frontmatter.

## Edge cases

Missing/ambiguous evidence is an explicit terminal, never guessed success. Interrupted or denied work
retains cost and method attribution. Recheck user/session authority at execution and delivery.

## Out of scope

Inventory conversion, Stagehand removal, autonomous booking actions, provider/payer fallback and
claims of qualification without evidence.
