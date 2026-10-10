---
adr: ADR-056
status: accepted
created: "2026-10-10T01:46:00Z"
bolt: 089-jev-price-promotion
---

# ADR-056: Jev as the authoritative price method, LLM price path retained as rollback

## Context

ADR-055 ran Jev beside the Browser Use/Anthropic price method with baseline-only authority. Over
56 paired checks in six days the LLM method cost USD 11.65 and Jev USD 0.08; both verified the
same price in all 23 pairs where both succeeded; Jev verified 37 of 56 checks and the LLM method
29. Price checks were the deployment's entire Anthropic spend that week (USD 12.12). One booking
with a member-discounted room never verified under Jev. The owner decided on 2026-10-06 to stop
running the LLM price method in production and keep its code.

## Decision

Add `jev` as a value of the existing price-executor selector. When selected, Jev's validated
observation is the canonical result and may refresh the saved session; no Anthropic price call is
made. Jev keeps its own credential, pinned model, per-check call cap, daily nano-USD cap and a
durable per-run cost and diagnostic record. Paired mode cannot be enabled at the same time. The
Browser Use and Stagehand price adapters remain in the code and selectable by config. Removing
them, or returning to them, is a later owner decision tracked in a GitHub issue.

## Rationale

The selector and provider-neutral port already exist, so authority moves without touching
validation, equivalence, savings or alerts. Keeping the LLM adapters costs nothing at runtime and
makes rollback a config edit.

## Consequences

Savings alerts now depend on Jev's observation; the unchanged validators and code-side grounding
remain the safeguard. Booking page text for every user goes to TypeSafe on each price check.
Reservation discovery is unchanged. Six days on three bookings is a small sample: the decision is
revisited through the tracking issue, and each run's diagnostic records why a check produced no
price. Amends ADR-055 (authority) and ADR-043 (adds a third selectable price executor kind).
