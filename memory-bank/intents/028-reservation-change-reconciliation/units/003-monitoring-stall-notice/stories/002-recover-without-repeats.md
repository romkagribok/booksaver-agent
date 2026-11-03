---
id: 002-recover-without-repeats
unit: 003-monitoring-stall-notice
intent: 028-reservation-change-reconciliation
status: complete
priority: must
created: "2026-11-02T20:51:19Z"
assigned_bolt: 095-monitoring-stall-notice
implemented: true
---

# US-238: Report recovery without repeats

## User story

As a BookSaver user, I want one message for a stall and one for its recovery, so that alerts stay meaningful.

## Assigned requirement

FR-8.

## Acceptance criteria

- [ ] Given a notified stall, when later runs still stall, then no repeat is sent, including after a daemon restart.
- [ ] Given a notified stall, when a conclusive result arrives, then one recovery message is sent.
- [ ] Given a recovered reservation, when it stalls again, then a new notice is sent.
- [ ] Given an archived or past reservation, when evaluated, then nothing is sent.

## Out of scope

Escalation to the owner about another user's booking.
