---
id: 005-finalize-verified-remote-authentication-atomically
unit: 002-dom-resilient-browser-workflows
intent: 022-adaptive-booking-browser-resilience
status: complete
priority: must
created: 2026-08-14T03:08:12.000Z
assigned_bolt: 046-dom-resilient-browser-workflows
implemented: true
---

# Story: Finalize Verified Remote Authentication Atomically

## User Story

**As a** BookSaver user completing Booking.com authentication
**I want** a code-verified login to be saved and acknowledged before the streamed viewer closes
**So that** manually closing a finished-looking viewer cannot turn successful authentication into a
cancelled attempt

## Acceptance Criteria

- [x] **Given** the viewer is ready or connected but authentication is not code-verified, **When**
  the user explicitly cancels or abandons it, **Then** the attempt cancels and saves no session.
- [x] **Given** a fresh code verification receipt proves authenticated inventory, **When** the
  runner begins finalization, **Then** the attempt enters a visible `finalizing` state and ordinary
  viewer close cancellation is ignored.
- [x] **Given** finalization is active, **When** administrative purge/revocation or daemon shutdown
  occurs, **Then** that higher-authority cancellation remains fail-closed and prevents persistence.
- [x] **Given** verified cookies are returned after browser cleanup, **When** encrypted persistence
  succeeds, **Then** BookSaver commits `succeeded`, records the assisted recovery, notifies Telegram,
  and allows the Mini App to close in that order.
- [x] **Given** encrypted persistence rejects the cookies, **When** finalization completes, **Then**
  the attempt becomes `failed` with capture-specific safe guidance and no recovered incident.
- [x] **Given** the viewer polls `succeeded`, **When** Telegram Mini App close capability is present,
  **Then** it calls `tg.close()`; other terminal failures remain visible for the user to read.
- [x] **Given** any finalization outcome, **When** runtime logs and incident metadata are inspected,
  **Then** they contain only safe stage/outcome codes and exception class, never cookies, tokens,
  user identity, page content, or reservation data.

## Technical Notes

- Separate viewer-originated cancellation from administrative purge cancellation during the narrow
  verified-to-committed window.
- Move recovered-incident publication to the manager boundary after successful encrypted capture.
- Preserve the existing post-browser-cleanup evidence boundary and browser/coordinator gate ownership.

## Dependencies

### Requires

- US-134, US-135, and US-136.
- Bolts 031, 042, 043, 044, and 045.

### Enables

- Reliable human acceptance of the remote-auth DOM recovery release.

## Edge Cases

| Scenario | Expected Behavior |
|----------|-------------------|
| Page closes immediately after verification | Viewer cancellation is ignored; commit completes or returns typed failure |
| User cancels before verification | Cancellation wins; no session or recovery incident |
| Admin purges during finalization | Purge/revocation wins; no session can survive |
| Capture raises after browser cleanup | Failed terminal state, safe log code, no false recovered occurrence |
| Telegram close API is unavailable | Succeeded status remains visible; session is already committed |

## Out of Scope

- Changing DOM classification, model routing, credentials, cookies format, or Booking.com navigation.
- Weakening user purge, daemon shutdown, encryption, or protected-browser boundaries.
