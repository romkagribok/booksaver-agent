---
id: 007-enter-browser-use-inventory-through-canonical-https
unit: 004-agentic-inventory-executor
intent: 023-replaceable-agentic-browser-executor
status: in-progress
priority: must
created: 2026-08-30T22:28:13Z
assigned_bolt: 061-agentic-inventory-executor
implemented: true
---

# Story: Enter Browser Use Inventory through Canonical HTTPS

## User Story

**As a** BookSaver user
**I want** `/bookings` to open the current protected inventory page without traversing an insecure
legacy redirect
**So that** Browser Use reaches authenticated inventory reliably while BookSaver keeps HTTPS-only
egress and read-only safety boundaries intact

## Acceptance Criteria

- [ ] Browser Use starts at the code-owned HTTPS `secure.booking.com/mytrips.html` inventory route.
- [ ] The shared Stagehand entry and every non-`/bookings` trigger remain unchanged.
- [ ] BookSaver does not allow HTTP egress or add a redirect exception for the legacy
  `myreservations` route.
- [ ] A safe inspected Booking.com link with `target=_blank` is normalized to the same tab after
  destination validation; no popup is created and unsafe or missing targets remain rejected.
- [ ] A regression test proves the Browser Use entry is HTTPS `mytrips`, while the network guard
  continues to reject the observed HTTP redirect.
- [ ] Aggregate text from non-interactive structural ancestors is not treated as the clicked
  control's label; interactive ancestors, attributes, event handlers, and destinations remain
  guarded and a click with no interactive ancestor is rejected.
- [ ] A proposal rejected before execution consumes the action allowance, emits only a bounded
  reason code, and lets Browser Use choose another inventory control within the existing caps.
- [ ] App-install, footer, promotion, account, and unrelated controls are excluded from the agent
  task; app-install/download routes remain denied before replay.
- [ ] A bounded production replay reaches inventory perception and completes positive discovery
  without requiring a Telegram command between iterations.
- [ ] BookSaver may provide bounded caller-owned saved confirmation IDs as redacted search hints;
  Browser Use can submit one only when the exact number is visibly re-observed, and the hint cannot
  authorize absence, eligibility, or any action.
- [ ] When the number is hidden, Browser Use may propose a saved candidate only with the exact
  visible property and stay dates; BookSaver compares those facts to its caller-owned record before
  supplying identity, and any mismatch is rejected without persistence.

## Dependencies

- US-160 and ADR-041.

## Out of Scope

- Broadening destination or action authority, changing authentication proof, adding selectors,
  changing Stagehand routes, allowing absence reconciliation, or increasing cost/action/time caps.
