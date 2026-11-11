---
id: 001-cancellation-ended
unit: 001-legible-reports
intent: 040-legible-reports
status: draft
priority: must
created: "2026-11-11T00:10:37Z"
assigned_bolt: 113-legible-reports
implemented: false
---

# Story: US-265 A passed free-cancellation date is read as ended

## User Story

**As a** BookSaver user
**I want** a booking whose free cancellation has ended to be recorded that way
**So that** its terms are known and reported correctly

## Acceptance Criteria

- [ ] **Given** Jev reads "free until a date" and the date has passed, **When** synced, **Then** the reservation is not refundable with the note "Free cancellation ended on <date>." and counts as read.
- [ ] **Given** a future free-cancellation date, **When** synced, **Then** it is refundable with that deadline as before.
- [ ] **Given** a deadline after check-in, **When** synced, **Then** the terms stay unread.

## Dependencies

### Requires
- None

### Enables
- None

## Out of Scope

- Admin, incident and sign-in replies.
