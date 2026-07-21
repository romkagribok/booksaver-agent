---
stage: model
bolt: 025-authenticated-mobile-web-monitoring
created: 2026-07-19T21:23:00Z
---

# Domain Model: Authenticated Mobile-Web Monitoring

## Concepts

- **MobileWebProfile**: Allowlisted Playwright device identity and locale/timezone configuration.
- **AuthenticatedCheckContext**: Booking owner + session revision + mobile profile.
- **AuthenticationEvidence**: Rendered proof of logged-in state or typed failure.
- **GeniusEvidence**: `applied_or_present`, `not_observed`, or `indeterminate`.
- **PriceSourceProvenance**: Non-secret proof attached to a check result.

## Invariants

1. A price cannot be accepted without owner-bound ready session, validated mobile profile, and
   rendered authenticated context.
2. `not_observed` Genius evidence is valid; `indeterminate` authentication/pricing is not.
3. Provenance and Money succeed together; neither can be partially accepted.
4. Existing exact-property/date/occupancy/room/refundability/currency gates remain authoritative.
5. LLM recovery and mobile layout adaptation remain inside action/cost/context guards.
6. Final destructive action remains outside the automated aggregate on the real user device.

## Services and Ports

- **MobileContextFactory**: profile + session snapshot → fresh configured browser context.
- **AuthenticatedContextVerifier**: page → authentication/Genius evidence.
- **PriceProvenanceFactory**: context/evidence/timestamp → redacted provenance.
- **SearchMonitor**: consumes authenticated context and returns result + provenance atomically.

## Events

- Authenticated mobile context validated, Genius evidence observed/not-observed, source rejected,
  and price accepted with provenance.

## Story Coverage

The model covers US-083 through US-088.
