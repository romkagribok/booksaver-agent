---
id: ADR-028
title: Gate absence reconciliation on complete inventory traversal
status: accepted
created: 2026-07-27T16:33:44Z
bolt: 034-booking-account-sync-core
---

# ADR-028: Gate Absence Reconciliation on Complete Inventory Traversal

## Context

Booking.com's dynamic authenticated pages may paginate, vary by locale/account, partially load, or
encounter bot walls and rate limits. Treating an unseen reservation as cancelled or removed after a
partial traversal would incorrectly archive monitoring and invalidate savings.

## Decision

Every discovery result explicitly classifies inventory enumeration as `complete`, `incomplete`, or
`failed`. Positive observations may reconcile during complete or incomplete runs. Only a complete
run with recognized terminal traversal evidence may transition a previously synchronized but unseen
reservation to `absent`.

Failed runs change no reservation snapshot. Incomplete/failed runs retain prior state and expose
stale/failure status. Explicit lifecycle labels on positively observed reservations remain usable
without relying on absence.

For the supported Booking.com inventory, complete traversal requires both:

- a bounded wait for a stable rendered list, explicit empty state, or structured reservation payload;
- explicit all-scope evidence or successful terminal traversal of upcoming, past, and cancelled
  scopes, including every discovered pagination link.

The absence of a link or an empty upcoming view is not evidence that the other scopes are empty.

## Rationale

- Positive evidence and inventory absence have different proof requirements.
- Completeness as a domain value is inspectable, testable, and fail-closed.
- The rule tolerates UI drift without silently corrupting monitoring state.

## Consequences

- Browser adapters must define dynamic-render readiness, scope coverage, terminal pagination
  evidence, and bounded traversal.
- Reconciliation APIs carry completeness explicitly.
- Partial runs can improve observed records but cannot remove unseen ones.
- User/operator output distinguishes intrinsic lifecycle from stale synchronization state.
