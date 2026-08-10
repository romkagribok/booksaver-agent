---
id: 004-recover-initial-inventory-navigation-from-current-evidence
unit: 002-agent-assisted-booking-inventory
intent: 021-booking-browser-llm-recovery
status: complete
priority: must
created: 2026-08-10T16:36:20.000Z
assigned_bolt: 040-agent-assisted-booking-inventory
implemented: true
---

# Story: Recover Initial Inventory Navigation from Current Evidence

## User Story

**As a** BookSaver user relying on authenticated reservation monitoring
**I want** inventory recovery to inspect the page that exists after a navigation failure
**So that** a stale fresh-browser page cannot disable synchronization while all safety boundaries remain intact

## Acceptance Criteria

- [x] **Given** a fresh browser begins on `about:blank`, **When** inventory navigation reaches an
  allowlisted authenticated Booking.com reservation page but readiness raises, **Then** recovery uses
  a new current-page observation and does not classify the stale pre-navigation page as the current
  destination.
- [x] **Given** a fresh current reservation-page observation, **When** guarded recovery begins,
  **Then** the pre-navigation observation is used only as a progress baseline and the existing named
  verifier remains authoritative.
- [x] **Given** the current page cannot be observed after a navigation exception, **When** recovery
  classifies the failure, **Then** it fails unavailable without invoking the LLM or executing a
  browser action.
- [x] **Given** the current page is authentication, captcha, external, or prohibited, **When**
  recovery classifies it, **Then** the existing specific fail-closed boundary wins before any LLM
  call or action.
- [x] **Given** a navigation/readiness exception, **When** operator logs are inspected, **Then** they
  include only the recovery step, exception class, and bounded destination category and exclude the
  exception message, URL, query, page text, reservation identity, cookies, and provider content.
- [x] **Given** an incomplete or failed run, **When** reconciliation and `/checknow` complete, **Then**
  preserved inventory is not overwritten and no price check starts from stale data.

## Technical Notes

- Separate post-failure safety evidence from the pre-navigation progress baseline in
  `BookingComAccountInventorySource._recover_navigation`.
- Do not broaden the Booking.com route allowlist or guess new DOM selectors without current evidence.
- Cover the production `inventory_upcoming_url` shape with deterministic fake-browser tests.

## Dependencies

### Requires

- US-126 through US-128 and completed bolt 039.
- ADR-027, ADR-028, and ADR-030.

### Enables

- Restored production inventory synchronization and monitored price checks after reviewed deployment.

## Edge Cases

| Scenario | Expected Behavior |
|----------|-------------------|
| Current observation is allowlisted after readiness timeout | Enter guarded recovery from current evidence |
| Current observation is unavailable | Fail unavailable; no stale fallback, LLM call, or action |
| Current observation is `about:blank` or external | Fail closed as unapproved; no LLM call or action |
| Exception message or URL contains private data | Diagnostic emits categories only |

## Out of Scope

- Broadening allowlisted destinations without separately captured and reviewed Booking.com evidence.
- Automating authentication, MFA, cancellation, modification, checkout, payment, or purchase.
- Merging, deploying, or running a second live browser coordinator before the owner review gate.
