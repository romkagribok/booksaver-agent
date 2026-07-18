---
id: 003-select-bookings-and-savings-opportunities
unit: 001-interactive-command-navigation
intent: 005-telegram-command-navigation
status: complete
priority: must
created: 2026-07-18T22:14:33.000Z
assigned_bolt: 016-interactive-command-navigation
implemented: true
---

# Story: Select Bookings and Savings Opportunities

**Global story ID**: US-045

## User Story

**As an** authorized Telegram user
**I want** to tap my booking or savings opportunity after selecting a command
**So that** I never have to copy opaque identifiers from another message

## Acceptance Criteria

- [ ] **Given** I send `/checks` without an ID, **When** I own bookings, **Then** buttons show their
  property and stay context and a tap renders the selected booking's recent checks.
- [ ] **Given** I send `/rebook` without an ID, **When** I have savings opportunities, **Then** buttons
  show recognizable savings context and a tap starts the existing guided session.
- [ ] **Given** I type an exact supported identifier, **When** the command runs, **Then** existing typed
  behavior remains available.
- [ ] **Given** a forged/stale/cross-user callback, **When** it is tapped, **Then** BookSaver discloses
  nothing and starts no rebook operation.

## Technical Notes

- Encode authoritative UUIDs, not labels, within the callback size bound.
- Reuse one operation function for typed and callback invocation.

## Dependencies

### Requires

- US-044 callback router.

### Enables

- Identifier-free monitoring and guided rebooking.

## Edge Cases

| Scenario | Expected Behavior |
|----------|-------------------|
| User has no bookings/opportunities | Existing clear empty-state message |
| Selected entity is deleted after keyboard render | Non-disclosing stale result |

## Out of Scope

- Editing or deleting a booking.
