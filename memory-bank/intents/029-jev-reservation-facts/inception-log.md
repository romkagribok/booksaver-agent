---
intent: 029-jev-reservation-facts
created: "2026-11-03T19:24:37Z"
completed: "2026-11-03T21:24:43Z"
status: complete
---

# Inception Log: jev-reservation-facts

## Overview

**Intent**: Let Jev select, and code prove, the booked total and refund terms that the code reader
cannot read, so new layouts stop leaving reservations silently unmonitored.
**Type**: Enhancement

## Decision Log

| Date | Decision | Rationale | Approved |
|------|----------|-----------|----------|
| 2026-11-03 | Use Jev in syncs the way price checks use it | "Pure code checking can never cover all options" | Owner |
| 2026-11-03 | One solution, Jev from the start; ignore deadlines; robust and lean | Owner instruction | Owner |
| 2026-11-03 | Read-only checks on any account need no approval | Owner instruction | Owner |
| 2026-11-03T19:24:37Z | Proposed: Jev selects, code proves; no model-only facts | Keeps ADR-058/059 trust; no labelled tier needed | Owner |
| 2026-11-03T21:24:43Z | Requirements, plan, and sending candidate price and refund lines to TypeSafe approved | "I approve both, proceed" | Owner |
| 2026-11-03T21:24:43Z | Stops: none per stage; one before commit, merge and deploy (as intent 028) | Offered with the plan and approved | Owner |

