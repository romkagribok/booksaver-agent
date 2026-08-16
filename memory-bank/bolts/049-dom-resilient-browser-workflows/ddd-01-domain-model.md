---
stage: model
bolt: 049-dom-resilient-browser-workflows
created: 2026-08-16T16:23:56Z
---

# Static Model: Exact Edge-Pending Negative Control

## Entities and Aggregates

- **BookingServerSessionVerifier** is the attempt-local aggregate root. It owns baseline admission,
  immutable candidate verification, receipt issuance, and one-use receipt consumption.
- **RemoteAuthServerReceipt** remains the only success authority. Contract v2, caller, attempt,
  expiry, verifier identity, and exact cookie-snapshot HMAC are invariant members.

## Value Objects

- **ServerResponseEvidence** contains only closed status, media, redirect, and size classes.
- **EdgePendingNegativeControl** is the exact response conjunction: status `202`, HTML media, no
  redirect, empty body, and the unchanged literal protected endpoint without query or fragment.
- **CandidateSessionSnapshot** is the canonical immutable Booking-cookie byte sequence and secret
  fingerprint retained only inside one attempt.

## Invariants

1. OAuth redirect and exact edge-pending evidence are negative outcomes only.
2. No negative outcome carries a receipt, saves cookies, closes the viewer, or spends a model call.
3. A candidate edge-pending result enters the existing bounded recheck path.
4. A `202` that differs in any field is not edge-pending and cannot be accepted as negative or
   positive evidence merely because its status is successful.
5. Authentication still requires two independent exact `200`, HTML, bounded, direct protected-path
   responses for the identical candidate snapshot.
6. Contract-v1 evidence and receipts cannot be consumed under contract v2.

## Domain Events

- **NegativeBaselineEstablished**: either approved v2 negative tuple admits the viewer.
- **CandidateStillSignedOut**: candidate receives an approved negative tuple and schedules a bounded
  recheck without finalization.
- **AuthenticatedSnapshotVerified**: two exact positive probes issue the bound v2 receipt.
- **ServerContractRejected**: any non-approved response fails closed with content-free evidence.

## Domain Services

- **ClassifyServerResponse** applies protected redirect/challenge/availability/size checks before the
  two exact negative predicates and the exact positive predicate.
- **VerifyCandidateTwice** preserves independent contexts and identical candidate bytes.

## Repository Interfaces

No persistence interface changes. Evidence remains content-free and existing incident storage is
used only for genuinely changed contracts.

## Ubiquitous Language

- **Edge-pending**: the observed empty `202` response from a cookie-free protected probe; it proves
  no authentication and only permits the login flow to remain interactive.
- **Negative control**: an exact code-owned response known not to authorize session capture.
- **Positive contract**: the unchanged exact direct bounded `200` response required twice.
