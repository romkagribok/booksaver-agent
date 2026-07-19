---
stage: model
bolt: 023-post-rebook-monitoring
created: 2026-07-19T19:53:22Z
---

# Static Model: Post-Rebook Monitoring

## Bounded Context

Post-rebook monitoring begins after the existing guided workflow has handed actions to the user's
device. It does not execute cancellation or purchase. It interprets the user's reports, validates
actual replacement facts, and changes only BookSaver's local monitoring disposition.

## Entities

- **Monitored Booking**: Stable BookSaver identity plus owner, reservation identity, equivalence
  criteria, actual baseline, status, and historical relationships. The aggregate may represent the
  original or its validated replacement, never both simultaneously.
- **Rebook Session**: Existing audit/session identity linking the savings opportunity and monitored
  booking. Only a completed session that sent a replacement handoff can enable propagation.
- **Savings Opportunity**: Historical detected offer. It triggers the guided flow but its live price
  is not proof of the replacement's paid amount.
- **Authorized User**: Active caller who owns the monitored booking. Ownership and access are required
  at final mutation time.

## Value Objects

- **Handoff Outcome**: `completed`, `abandoned`, or `unreported`, independently for cancellation and replacement.
- **Replacement Facts**: Actual confirmation ID, canonical same-property Booking.com reference, and actual all-in Money.
- **Source Snapshot**: Complete monitored-booking value at handoff; used as an optimistic consistency token.
- **Monitoring Disposition**: `replacement_active`, `original_active`, or `no_active_booking`.
- **Canonical Property Reference**: HTTPS Booking.com scheme/host/property path with query/fragment removed.

## Aggregate Invariants

1. A replacement becomes active only after replacement outcome `completed`, valid facts, and explicit final confirmation.
2. `SavingsOpportunity.live_price` never supplies the replacement baseline.
3. The final transaction requires active access, ownership, completed session linkage, and an unchanged source snapshot.
4. Stable booking ID and all linked historical rows survive replacement propagation.
5. Replacement propagation changes confirmation, canonical reference, actual Money, and status; equivalence fields remain unchanged.
6. A reported completed cancellation archives the source until/unless a validated replacement is activated.
7. Replacement/archive invalidates all savings for the stable booking ID.
8. Booking/savings/disposition-event changes commit or roll back together.

## Outcome Matrix

| Old cancellation | Replacement booking | Immediate disposition | Follow-up |
|------------------|---------------------|-----------------------|-----------|
| Completed | Completed | Archive source, collect facts | Activate validated replacement or remain archived |
| Completed | Abandoned | Archive source | Explain no booking is monitored |
| Completed | Unreported | Archive source | Explain no booking is monitored until user registers/repairs state |
| Abandoned | Completed | Keep source while collecting facts | Activate validated replacement; warn old may still exist |
| Abandoned | Abandoned | Keep original active | Explain original remains monitored |
| Abandoned | Unreported | Keep original active | Explain original remains monitored; replacement unknown |
| Unreported | Completed | Keep source while collecting facts | Activate validated replacement; warn cancellation unknown |
| Unreported | Abandoned | Keep original active | Explain original remains monitored; cancellation unknown |
| Unreported | Unreported | Keep original active | Explain both outcomes are unknown |

## Domain Events

- **SourceReservationArchived**: Triggered by a completed cancellation report; records session/disposition and invalidates savings.
- **ReplacementMonitoringActivated**: Triggered by a confirmed valid replacement; records actual total/currency and activates the stable aggregate.
- **ReconciliationRejected**: User-visible result only; no persistent mutation when access/ownership/session/snapshot/facts fail.

## Domain Services

- **Outcome Reconciler**: Maps the two handoff outcomes to archive, fact collection, or unchanged disposition and final guidance.
- **Replacement Fact Validator**: Creates domain values and proves a Booking.com property reference is acceptable/same-property.
- **Monitoring Propagation Service**: Requests one guarded repository transaction for archive or replacement activation.

## Repository Interface

- **PostRebookRepository**:
  - `archive_cancelled_source(command) -> disposition`
  - `activate_replacement(command) -> updated booking`
  - Both operations validate user/session/source and append audit within one transaction.

## Ubiquitous Language

- **Detected offer**: A refundable equivalent price observed before checkout; not the paid receipt.
- **Actual total**: All-in amount/currency the user reports from the completed replacement booking.
- **Propagation**: Updating the stable monitored aggregate to represent the actual replacement.
- **Archive**: Marking the source inactive because the user reports it was cancelled.
- **Source snapshot**: Exact monitored state handed off before external user actions.
- **Disposition**: What BookSaver will monitor after reconciliation.

## Story Coverage

- US-072: Replacement Facts and validator.
- US-073: Aggregate invariants and activation transaction.
- US-074: Outcome matrix and archive rule.
- US-075: Domain events, stable history, stale-savings invalidation.
- US-076: Authorized User and guarded repository boundary.
