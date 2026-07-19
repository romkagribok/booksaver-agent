---
id: 003-reconcile-partial-outcomes-safely
unit: 001-post-rebook-monitoring
intent: 011-post-rebook-monitoring
status: complete
priority: must
created: 2026-07-19T19:50:29.000Z
assigned_bolt: 023-post-rebook-monitoring
implemented: true
---

# Story: Reconcile Partial Outcomes Safely

**Global story ID**: US-074

## User Story

**As a** user who may finish only part of a rebook
**I want** BookSaver to reflect what actually happened
**So that** it never monitors a reservation I cancelled or invents one I abandoned

## Acceptance Criteria

- [ ] All completed/abandoned/unreported cancellation and replacement combinations are deterministic.
- [ ] Completed cancellation without validated replacement archives the old booking.
- [ ] No completed replacement leaves the original unchanged unless cancellation was reported complete.
- [ ] Completed replacement activates only after valid facts/final confirmation and warns on duplicate/unknown cancellation.

## Dependencies

- US-072 and US-073.
