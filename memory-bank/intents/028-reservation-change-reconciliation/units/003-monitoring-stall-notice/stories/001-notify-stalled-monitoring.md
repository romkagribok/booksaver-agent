---
id: 001-notify-stalled-monitoring
unit: 003-monitoring-stall-notice
intent: 028-reservation-change-reconciliation
status: complete
priority: must
created: "2026-11-02T20:51:19Z"
assigned_bolt: 095-monitoring-stall-notice
implemented: true
---

# US-237: Tell the user monitoring has stalled

## User story

As a BookSaver user, I want to know when a reservation stops being checked, so that I can look myself.

## Assigned requirement

FR-7.

## Acceptance criteria

- [ ] Given a monitored upcoming reservation with no conclusive result for 24 hours, when a scheduled run ends, then its own user gets one message.
- [ ] Given the cause, when the message is written, then it says sync failing, total unconfirmed or price checks failing in plain words.
- [ ] Given a verified "no equivalent offer", when evaluated, then it counts as conclusive.
- [ ] Given a session with a sign-in or uncertain-session notice, when evaluated, then no stall notice is sent.
- [ ] Given two users, when one stalls, then the other receives nothing.

## Out of scope

Operator dashboards.
