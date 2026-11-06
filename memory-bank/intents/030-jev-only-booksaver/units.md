---
intent: 030-jev-only-booksaver
phase: inception
status: units-decomposed
created: "2026-11-04T15:34:52Z"
updated: "2026-11-04T15:34:52Z"
---

# Jev-only BookSaver - Unit Decomposition

## Units Overview

### Unit 1: 001-jev-reservation-reader

Jev alone reads totals and refund terms. Bolt `098-jev-reservation-reader`, stories US-243 to US-245. FR-1 to FR-6.

### Unit 2: 002-no-anthropic-key

Everyone on Jev, inform invitees once, no Claude discovery fallback, start without the key. Bolt
`099-no-anthropic-key`, stories US-246 to US-248. FR-7 to FR-10.

### Unit 3: 003-delete-claude-code

Delete the Claude-only code. Bolt `100-delete-claude-code`, stories US-249 and US-250. FR-11, FR-12.

### Unit 4: 004-claude-data-config-docs

Drop Claude tables, retire config keys, update docs and issues. Bolt `101-claude-data-config-docs`,
stories US-251 to US-253. FR-13 to FR-15.

## Unit Dependency Graph

```text
001-jev-reservation-reader -> 002-no-anthropic-key -> 003-delete-claude-code -> 004-claude-data-config-docs
```

## Execution Order

One release per unit, in order; each deploys after the previous one is verified in production.
