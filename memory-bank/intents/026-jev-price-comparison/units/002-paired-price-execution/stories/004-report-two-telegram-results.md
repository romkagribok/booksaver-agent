---
id: 004-report-two-telegram-results
unit: 002-paired-price-execution
intent: 026-jev-price-comparison
status: draft
priority: must
created: "2026-09-26T16:33:08Z"
assigned_bolt: 086-paired-price-execution
implemented: false
---

# US-212: Report two Telegram results

## User story

As a user, I want to compare both methods in Telegram even when one fails, so the price comparison is trustworthy and actionable.

## Assigned requirement

FR-9; shared NFRs in ../../../requirements.md. The complete pair contract is in
../../../experiment-design.md.

## Acceptance criteria

- [ ] Given completed or partially failed manual/scheduled pair, when reporting, then show two labelled rows including validated result or reason, method cost/certainty, duration and comparison ID.
- [ ] Given no savings, unavailable Jev or incomplete evidence, when reporting, then both rows still appear and incomplete is never presented as a verified no-offer outcome.
- [ ] Given baseline savings, when notifying, then its canonical event persists once and its Telegram content is incorporated without a redundant savings message; email policy remains unchanged.
- [ ] Given duplicate callbacks, known send success or ambiguous Telegram timeout, when retries happen, then durable delivery identity prevents avoidable duplicates, records unknown delivery and does not rerun checks.
- [ ] Given invitees and provider errors, when composing, then use only the recipient booking/method data with no owner-wide usage, secrets or candidate reconnect/key warning; revoked recipients receive nothing.

## Technical notes

See experiment-design.md for sample copy, uncertainty labels and network exactly-once limits.

## Dependencies

Requires: US-210, US-211.
Assigned bolt: 086-paired-price-execution. Downstream dependencies are recorded in units.md and bolt frontmatter.

## Edge cases

Missing/ambiguous evidence is an explicit terminal, never guessed success. Interrupted or denied work
retains cost and method attribution. Recheck user/session authority at execution and delivery.

## Out of scope

Inventory conversion, Stagehand removal, autonomous booking actions, provider/payer fallback and
claims of qualification without evidence.
