---
unit: 001-post-rebook-monitoring
bolt: 023-post-rebook-monitoring
id: ADR-023
title: Stable-ID atomic post-rebook propagation
status: accepted
updated: 2026-07-19T19:55:13Z
---

# ADR-023: Stable-ID atomic post-rebook propagation

## Context

The Telegram guided-rebook flow hands cancellation/purchase to the user's device. Its detected
savings opportunity is not a checkout receipt, and its completion currently leaves the original
Booking aggregate and baseline unchanged. After a real replacement, BookSaver must either create a
second booking and retire the first, or change the existing monitored aggregate while preserving its
historical relationships. Partial flows also create a period where the user may have cancelled the
source without finishing replacement details.

## Decision

Treat a validated replacement as the next reservation represented by the same stable BookSaver
booking ID. Collect actual confirmation, canonical same-property Booking.com URL, and actual all-in
Money from the user; then use one guarded SQLite transaction to update those fields, reactivate the
aggregate, delete stale savings, and append a disposition audit event. A completed cancellation is
archived immediately before transient replacement-detail collection and can be reactivated only by
that validated replacement transaction.

## Rationale

- Stable identity preserves check history, traces, rebook sessions/events, ownership, and scheduler references.
- User-supplied actual checkout facts avoid false savings caused by treating a detected offer as paid.
- One transaction closes ownership/revocation/concurrency gaps between validation and write.
- Immediate archive makes dialog cancellation, timeout, or daemon restart fail safe after a reported cancellation.
- Updating only reservation identity/reference/baseline preserves the opportunity's verified equivalence criteria.

## Consequences

- The old confirmation is no longer on the booking row; the rebook audit event is the durable transition record.
- A completed cancellation followed by abandoned details leaves the stable booking archived and requires the user to finish propagation or register a replacement.
- No schema migration is needed, but repository operations must validate session/handoff/source state inside an immediate transaction.
- Authenticated receipt verification remains future work; the explicit user report/final confirmation is the current trust boundary.
