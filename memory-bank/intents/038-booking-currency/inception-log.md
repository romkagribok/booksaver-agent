---
intent: 038-booking-currency
created: "2026-11-10T13:26:27Z"
completed: "2026-11-10T13:26:27Z"
status: complete
---

# Inception Log: booking-currency

## Overview

**Intent**: Bookings are stored and checked in the currency they were made in.
**Type**: Bug fix (data correctness)

## Decision Log

| Date | Decision | Rationale | Approved |
|------|----------|-----------|----------|
| 2026-11-10 | Fix the saved currency, not the price check | Checks already follow the saved currency and reject other currencies | Owner request; engineering |
| 2026-11-10 | Jev states the currency; code checks the total matches it | Two independent answers in the same calls; no word rule for "approx." | Engineering |
| 2026-11-10 | Human checkpoints skipped | Standing waiver, CLAUDE.local.md point 4 | Owner standing waiver |
