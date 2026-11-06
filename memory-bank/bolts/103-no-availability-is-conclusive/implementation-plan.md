---
stage: plan
bolt: 103-no-availability-is-conclusive
created: 2026-11-06T16:53:03Z
---

# Implementation Plan

In `LocalJevPriceRuntime._extract`, when no rate job exists (no room named), ask Jev one question
with the room card lines and the requested dates: rooms listed for exactly these dates / only other
dates, sold out or no availability / unclear. At confidence 0.8 or more for the second option,
`_extract` returns `PriceExecutionStatus.UNAVAILABLE`, which `execute` passes through and the
monitor already maps to `no_equivalent_offer`. Diagnostics record `availability=unavailable`.
Tests with the existing fake decider; staging on Kalipè's page.
