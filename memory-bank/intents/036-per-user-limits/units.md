---
intent: 036-per-user-limits
phase: inception
status: units-decomposed
created: "2026-11-10T00:46:00Z"
updated: "2026-11-10T00:46:00Z"
---

# Unit Decomposition

## Units Overview

### Unit 1: 001-per-user-jev-cap

Bolt `107-per-user-jev-cap`, story US-259. FR-1 to FR-3.

### Unit 2: 002-remove-booking-cap

Bolt `108-remove-booking-cap`, story US-260. FR-4. Added 2026-11-10 at the owner's request.

## Unit Dependency Graph

```text
001-per-user-jev-cap
002-remove-booking-cap   (independent)
```

## Execution Order

One release.
