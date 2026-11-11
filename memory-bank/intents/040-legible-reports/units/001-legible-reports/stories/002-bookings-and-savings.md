---
id: 002-bookings-and-savings
unit: 001-legible-reports
intent: 040-legible-reports
status: draft
priority: must
created: "2026-11-11T00:10:37Z"
assigned_bolt: 113-legible-reports
implemented: false
---

# Story: US-266 /bookings and /savings are legible

## User Story

**As a** BookSaver user
**I want** my reservations and savings described by hotel, dates and amounts
**So that** I understand them without internal IDs

## Acceptance Criteria

- [ ] **Given** a refundable reservation with a deadline, **When** I send /bookings, **Then** it shows "Free cancellation until <d Mon yyyy>" and the stay as "12 – 15 Nov 2026".
- [ ] **Given** a reservation without free cancellation, **When** listed, **Then** the reason reads "no free cancellation".
- [ ] **Given** a saving, **When** I send /savings, **Then** it shows the hotel, stay, price paid, price found, saving and when it was found, with no IDs.

## Dependencies

### Requires
- None

### Enables
- None

## Out of Scope

- Admin, incident and sign-in replies.
