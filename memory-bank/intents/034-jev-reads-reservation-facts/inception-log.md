---
intent: 034-jev-reads-reservation-facts
created: "2026-11-08T18:31:21Z"
completed: "2026-11-08T18:31:21Z"
status: complete
---

# Inception Log: jev-reads-reservation-facts

## Overview

**Intent**: Jev reads the booked party, meals and (when needed) dates.
**Type**: Feature (robustness)

## Decision Log

| Date | Decision | Rationale | Approved |
|------|----------|-----------|----------|
| 2026-11-08 | Three releases: A sync facts, B price checks, C discovery | Smaller, verifiable releases | Owner: "Sounds good proceed" |
| 2026-11-08 | Dates code-first, Jev fills | Jev-only dates would make every sync incomplete during a TypeSafe outage | Engineering; reported to owner |
| 2026-11-08 | Unsure meal plan stays unknown | Guessing "no meals" risks false savings alerts | Owner agreed to "unsure means don't compare" |
