---
unit: 003-monitoring-stall-notice
bolt: 095-monitoring-stall-notice
stage: model
status: complete
created: 2026-11-03T01:27:07Z
updated: 2026-11-03T01:27:07Z
---

# Static Model - Monitoring Stall Notice

## Bounded Context

Per-user visibility of whether each monitored reservation is really being checked.

## Domain Entities

- **Monitored reservation**: an upcoming reservation with a monitoring booking whose stay has not
  ended, and which is eligible or held. A reservation made non-refundable is not monitored by
  design, so it never stalls.
- **Stall notice**: a durable record that the user was told, one per booking.

## Value Objects

- **Conclusive result**: a verified price or a verified "no equivalent offer".
- **Stall reason**: sync failing, total unconfirmed, or price checks failing, in that precedence.

## Domain Rules

1. Stalled means 24 hours without a conclusive result, counted from the later of the last conclusive
   result and the reservation's first observation.
2. One notice per stall; one recovery message when it ends; a new stall gives a new notice.
3. Nothing is sent while the session is not ready, because a session notice covers that.
4. A notice is recorded only after delivery, so a failed send retries on the next run.
5. A reservation that ends or stops being monitored drops its notice silently.

## Ubiquitous Language

**Stall**: a monitored reservation with no conclusive result for 24 hours.
