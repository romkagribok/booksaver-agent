---
id: 003-show-aggregate-admin-usage
unit: 001-telegram-privacy-boundaries
intent: 010-telegram-privacy-boundaries
status: complete
priority: must
created: 2026-07-19T02:34:19Z
assigned_bolt: 022-telegram-privacy-boundaries
implemented: true
---

# Story: Show Aggregate Admin Usage

**Global story ID**: US-069

## User Story

**As the** owner/admin
**I want** identity, access state, and aggregate usage without exact user records
**So that** I can operate the shared bot while respecting invited users' booking privacy

## Acceptance Criteria

- [ ] Admin rows show username/fallback label, access state, active-booking count, checks today, and
  LLM calls today; role appears only where operationally useful.
- [ ] In-memory counts are labeled `today (resets at UTC midnight and daemon restart)`.
- [ ] Admin output omits chat IDs, key state, exact domain identifiers/content, prices, outcomes,
  failures, savings, traces, and rebook events.
- [ ] Revoke/purge callbacks display identity only and carry an internal user ID.
- [ ] A dedicated aggregate query/projection prevents admin formatting from loading exact records.
- [ ] A narrow injected provider supplies coordinator counter snapshots and reports usage unavailable
  when absent; it never fabricates zero runtime usage.

## Technical Notes

- Feed CheckCoordinator snapshots into the projection through a small read-only provider and use SQL
  aggregate counts rather than materializing bookings.
- Keep an explicit allowlist DTO; avoid passing `Booking`, `CheckResult`, or `SavingsOpportunity`.
- Username is display-only and comes from Intent 009; fallback must not expose Telegram chat ID.

## Dependencies

### Requires

- Intent 009 username persistence and admin identity display.
- US-068 separation between scoped exact data and aggregates.

### Enables

- US-071 negative admin-output contract.

## Edge Cases

| Scenario | Expected Behavior |
|----------|-------------------|
| User has no username | Show internal non-chat-ID fallback |
| Daemon restarted today | Counts restart at zero and label states the reset scope |
| User is revoked with retained bookings | Access state and approved aggregate counts only |
| User has detailed failures/savings | No outcome, error, price, or savings text in admin output |

## Out of Scope

- Billing-grade persisted analytics or historical usage charts.
- Exact per-check operational support through Telegram.
