---
unit: 004-jev-price-promotion
intent: 026-jev-price-comparison
phase: construction
status: in-progress
unit_type: backend
default_bolt_type: ddd-construction-bolt
created: "2026-10-10T01:45:00Z"
updated: "2026-10-10T01:45:00Z"
---

# Jev as the production price method

## Purpose and scope

Carry out the owner's adoption decision of 2026-10-06: make Jev the only production price-check
method, keep the Browser Use/Anthropic price path in the code as a config-selectable rollback, and
close the one gap the comparison exposed (member-discounted rate cards).

This is a bounded change inside the existing daemon: one more value for the existing
`agentic_browser.price_executor` selector, behind the unchanged provider-neutral price port.

## Assigned requirements

FR-13, FR-14, FR-15, FR-16. See ../../requirements.md (amendment of 2026-10-09).

## Domain concepts and operations

AuthoritativePriceMethod, JevPriceRun (spend/diagnostic ledger), DailyJevCap, CurrentVersusOriginalPrice.

## Stories

| Story | Title | Bolt |
|---|---|---|
| US-216 | Price member-discounted rate cards | 089-jev-price-promotion |
| US-217 | Run Jev as the price method with the LLM path as rollback | 089-jev-price-promotion |
| US-218 | Explain Jev runs that produce no price | 089-jev-price-promotion |
| US-219 | Recover from Booking.com's transient error page | 089-jev-price-promotion |

## Out of scope

Reservation discovery and login (they remain on the existing implementation), deleting the LLM
price adapters or Stagehand (tracked by a GitHub issue for a later decision), new consent flows.
