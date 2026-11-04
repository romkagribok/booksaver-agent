---
id: 003-bound-and-surface-assisted-syncs
unit: 001-jev-reservation-facts
intent: 029-jev-reservation-facts
status: draft
priority: must
created: "2026-11-03T19:24:37Z"
assigned_bolt: 097-jev-reservation-facts
implemented: false
---

# US-242: Keep assisted syncs bounded and visible

## User story

As the owner, I want assisted syncs capped and unreadable stays reported, so that cost stays small and nothing is silently unmonitored.

## Assigned requirement

FR-6, FR-7, FR-8.

## Acceptance criteria

- [ ] Given the Jev daily cap reached, when syncing, then Jev is not asked and facts stay unknown.
- [ ] Given a page, when synced, then at most one question set is sent for it.
- [ ] Given an upcoming reservation unmonitored for 24 hours only because its total or refund terms are unknown, when a scheduled run ends, then its user gets one stall message; a non-refundable one never does.
- [ ] Given a sync, when it runs, then its limit is 300 seconds.
- [ ] Given the owner's dad's account on staging, when synced, then the four refundable stays become eligible.

## Out of scope

Jev for navigation.
