---
id: 001-desktop-profile-reads-prices
unit: 001-desktop-price-trial
intent: 041-desktop-price-trial
status: draft
priority: must
created: "2026-11-13T03:02:27Z"
assigned_bolt: 114-desktop-price-trial
implemented: false
---

# Story: US-268 A desktop profile reads a Booking.com price

## User Story

**As the** owner
**I want** the price reader to work on Booking.com's desktop page
**So that** a desktop reading can be compared with the mobile one

## Acceptance Criteria

- [ ] **Given** the desktop trial profile, **When** its context options are built from Playwright's "Desktop Chrome", **Then** they are accepted with `is_mobile` and `has_touch` false.
- [ ] **Given** `[browser] device_profile = "desktop-chromium"`, **When** config loads, **Then** it is rejected as unknown.
- [ ] **Given** a mobile profile, **When** its options are built from a desktop descriptor, **Then** they are rejected as before.
- [ ] **Given** a desktop room table with two rooms of two rates each, **When** the page is read, **Then** each room has its name and two rates, and each rate has its whole-stay price and cancellation lines.
- [ ] **Given** a rate row with a paid-breakfast amount and a room-count selector, **When** it is read, **Then** neither amount is among the rate's lines.
- [ ] **Given** a row that states fewer guests than the search, **When** the table is read, **Then** that row is not a rate.
- [ ] **Given** a mobile page with rate cards, **When** it is read, **Then** the result is the same as before this change.

## Technical Notes

`domain/mobile_web.py` (profile, validation), `browser_use_runtime.py` (emulation follows the
profile), `jev_page_snapshot.py` (table branch, used only when no rate card is present and
`#hprt-table` exists). Prototype evidence: public desktop pages, 2026-11-12.

## Dependencies

### Requires
- None

### Enables
- US-269

## Edge Cases

| Scenario | Expected Behavior |
|----------|-------------------|
| Discounted rate (original and current price inside hidden-from-screen-reader markup) | The current price line is read; the struck original is not |
| Room with one rate | One room, one rate |
| No room table and no rate cards | Existing generic fallback, unchanged |

## Out of Scope

- Any change to how amounts are grounded or offers validated.
