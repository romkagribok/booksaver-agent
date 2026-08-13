---
id: 003-recover-and-interpret-safe-dom-drift
unit: 002-dom-resilient-browser-workflows
intent: 022-adaptive-booking-browser-resilience
status: complete
priority: must
created: 2026-08-13T01:59:59.000Z
assigned_bolt: 043-dom-resilient-browser-workflows
implemented: true
---

# Story: Recover and Interpret Safe DOM Drift

## User Story

**As a** BookSaver user
**I want** visible semantic controls and facts to remain usable after Booking.com changes selectors
**So that** reservation synchronization and price checks keep working without unsafe guesses

## Acceptance Criteria

- [ ] **Given** a registered deterministic postcondition fails from changed visible structure,
  **When** current evidence and budgets are available, **Then** Sonnet receives the step goal,
  verifier, safe capabilities, outcomes, and bounded visual/structural observation.
- [ ] **Given** a visible safe control has a changed tag, role, test ID, or label, **When** the model
  selects its fresh element reference, **Then** step-specific guards and destination validation—not
  the old selector—decide whether the action may execute.
- [ ] **Given** one action opens a relevant Booking.com popup, **When** code verifies the popup is
  allowlisted, read-only, and unique, **Then** recovery may adopt it; any additional, external,
  protected, or mutating popup terminates safely.
- [ ] **Given** selectors can no longer prove a semantic postcondition, **When** a typed model
  observation agrees with trusted property, dates, occupancy, currency, refundability, identity,
  and fresh page evidence, **Then** the code verifier may accept semantic progress.
- [ ] **Given** model-derived reservation or offer facts are incomplete/conflicting/low-confidence,
  **When** validation runs, **Then** they cannot prove completeness, absence, identity, equivalence,
  eligibility, accepted price, or lifecycle mutation.
- [ ] **Given** any current trigger (`/bookings`, post-`/connect`, `/checknow`, scheduled sync, or price
  check), **When** the same DOM seam fails, **Then** it enters the same coordinator-owned resilience
  path without opening a second browser.

## Technical Notes

- Expand step-specific accessible-control handling, not arbitrary selectors/URLs/scripts.
- Add typed semantic verifier evidence to search postconditions and final offer extraction.
- Keep positive-only partial inventory behavior and deterministic terminal traversal proof.

## Dependencies

### Requires

- US-130 through US-134.

### Enables

- US-136 through US-139.

## Edge Cases

| Scenario | Expected Behavior |
|----------|-------------------|
| Popup destination cannot be observed | Do not adopt; exact observation reason |
| Unknown no-href button | Do not click speculatively; diagnose/incident instead |
| Model sees correct room but wrong currency | Reject semantic success and continue/diagnose |
| Inventory positives found without terminal scopes | Upsert permitted positives under partial rules; preserve unseen state |

## Out of Scope

- Arbitrary model-generated selectors, URLs, JavaScript, or coordinate actions.
- Any model-proposed protected or transactional action.
