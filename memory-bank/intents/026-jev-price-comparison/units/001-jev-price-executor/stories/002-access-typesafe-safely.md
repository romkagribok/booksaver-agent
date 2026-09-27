---
id: 002-access-typesafe-safely
unit: 001-jev-price-executor
intent: 026-jev-price-comparison
status: draft
priority: must
created: "2026-09-26T16:33:08Z"
assigned_bolt: 085-jev-price-executor
implemented: false
---

# US-205: Access TypeSafe safely

## User story

As a owner, I want to configure an isolated and bounded TypeSafe integration, so the price comparison is trustworthy and actionable.

## Assigned requirement

FR-3; shared NFRs in ../../../requirements.md. The complete pair contract is in
../../../experiment-design.md.

## Acceptance criteria

- [ ] Given valid deployment credentials and a pinned profile, when a request is admitted, then only the approved TypeSafe endpoint receives sanitized bounded text/options and the response model/version is validated.
- [ ] Given missing key, redirect, unexpected provider/model, malformed response or invalid pricing, when the client runs, then it fails closed with a typed reason and no substitute provider.
- [ ] Given overload, rate limit or timeout, when retry policy applies, then attempts honor residual deadline/call/cost caps and are individually metered; no invisible SDK retry.
- [ ] Given active invitees, when paired routing is evaluated, then TypeSafe disclosure is checked separately without inventing acknowledgement or breaking already-consented baseline-only checks.
- [ ] Given new secret and endpoint settings, when construction finishes, then AGENTS/standards/config examples and secret-redaction/egress tests match the new policy.

## Technical notes

Use direct server-side HTTP; prefer stdlib/existing facilities. No new gateway, SDK dependency or payer fallback without a recorded need.

## Dependencies

Requires: US-204.
Assigned bolt: 085-jev-price-executor. Downstream dependencies are recorded in units.md and bolt frontmatter.

## Edge cases

Missing/ambiguous evidence is an explicit terminal, never guessed success. Interrupted or denied work
retains cost and method attribution. Recheck user/session authority at execution and delivery.

## Out of scope

Inventory conversion, Stagehand removal, autonomous booking actions, provider/payer fallback and
claims of qualification without evidence.
