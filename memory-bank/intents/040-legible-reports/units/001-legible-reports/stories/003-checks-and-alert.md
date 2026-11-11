---
id: 003-checks-and-alert
unit: 001-legible-reports
intent: 040-legible-reports
status: draft
priority: must
created: "2026-11-11T00:10:37Z"
assigned_bolt: 113-legible-reports
implemented: false
---

# Story: US-267 /checks, /checknow and the alert speak plainly

## User Story

**As a** BookSaver user
**I want** check results and alerts in plain words
**So that** I know what happened without reading codes

## Acceptance Criteria

- [ ] **Given** checks of a booking, **When** I open /checks, **Then** the reply names the hotel, stay and price paid, and each line reads "<d Mon>, <HH:MM> UTC: <price>, <difference> below/above what you paid" or a plain reason.
- [ ] **Given** a check-now result with a saving under 5, **When** it completes, **Then** the reply says it is under the 5 <currency> alert minimum.
- [ ] **Given** any failure code, **When** shown, **Then** a plain sentence appears, never the code.
- [ ] **Given** an alert, **When** sent, **Then** it shows "Checked as: signed in to your Booking.com account" (with "Genius prices were shown" when present), not the browser profile.

## Dependencies

### Requires
- None

### Enables
- None

## Out of Scope

- Admin, incident and sign-in replies.
