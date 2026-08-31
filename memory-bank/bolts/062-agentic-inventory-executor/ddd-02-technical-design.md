---
stage: design
bolt: 062-agentic-inventory-executor
created: 2026-08-31T21:59:00Z
---

# Technical Design: Genuine Browser Use Inventory Discovery

## Architecture Pattern

Retain the existing provider-neutral executor and positive-only validation boundary. Correct only
the Browser Use adapter: every authenticated `/bookings` run reaches the agent, while semantic
saved matches remain an optional evidence tool rather than a terminal fast path.

## Layer Structure

- **Infrastructure adapter**: Remove the saved-row return; expose minimal strict identity and
  bounded optional-fact tools; continue visible upcoming enumeration through guarded actions.
- **Application/domain**: Reuse `ObservedReservation`, validation, compatibility merging,
  eligibility, and positive-only reconciliation without schema or authority changes.
- **Persistence**: Reuse confirmation-aware upsert. Unknown identities create account rows; sparse
  positives remain reason-coded ineligible until enough facts are visible.

## API Design

- `submit_inventory_observation(confirmation_id, scope, identity_evidence)`: stable current visible
  identity only.
- `submit_inventory_facts(confirmation_id, facts_json)`: bounded JSON string containing only
  provider-shaped optional fields. The handler requires a matching identity in the same episode,
  validates the allowlist and bounds, and merges through existing typed mapping.
- `submit_saved_inventory_match()`: still resolves one current visible caller-owned candidate but
  no longer implies `done`.

## Data Model

No migration. Existing confirmation-aware reconciliation and account reservation tables are used.

## Security Design

- No new browser authority, navigation target, provider secret, persisted content, or transaction
  capability.
- Fact JSON is bounded, decoded locally, never logged, and cannot create identity or absence.
- Every browser action remains guarded and metered before and after execution.
- Network admission permits only proper HTTPS `token.awswaf.com` subdomains for Booking's required
  WAF bootstrap. That domain remains excluded from observable destinations and agent actions.

## Reliability Design

- Identity and optional facts fail independently, preventing provider formatting variance from
  discarding a genuine new positive.
- The agent task requires scanning visible upcoming cards and does not stop merely because a known
  candidate matched.
- Qualification uses a cloned production data directory with reservation rows removed, retains the
  encrypted session, and asserts the live booking is newly inserted without changing production.

## ADR Analysis

ADR-039 continues to require positive-only inventory, ADR-040 separates observation from
interaction authority, and ADR-041 selects guarded local Browser Use for `/bookings`. Production
diagnostics exposed a new external subresource boundary, so ADR-042 records the narrow
Booking-required AWS WAF token exception and keeps it outside agent navigation authority.
