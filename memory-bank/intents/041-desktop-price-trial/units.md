---
intent: 041-desktop-price-trial
phase: inception
status: units-decomposed
created: "2026-11-13T03:02:27Z"
updated: "2026-11-18T13:00:53Z"
---

# One-week silent desktop price trial - Unit Decomposition

## Units Overview

### Unit 1: 001-desktop-price-trial

**Description**: The desktop profile and reader (FR-1, FR-2) and the silent reading after a
scheduled slot with its storage, config and guards (FR-3, FR-4). FR-5 is an operations step.

**Stories**: US-268, US-269, US-270. **Bolts**: `114-desktop-price-trial`, then
`115-retire-desktop-price-trial` (FR-6, added 2026-11-18 after the evaluation).

**Estimated Complexity**: M

## Unit Dependency Graph

```text
001-desktop-price-trial
```

## Execution Order

Bolt 114 and its release; then, after the evaluation, bolt 115 and the release that removes the
trial.
