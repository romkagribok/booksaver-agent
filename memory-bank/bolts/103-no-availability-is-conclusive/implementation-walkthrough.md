---
stage: implement
bolt: 103-no-availability-is-conclusive
created: 2026-11-06T17:10:30Z
---

# Implementation Walkthrough

`LocalJevPriceRuntime._extract` asks one more Jev question when no room type is named but cards
exist: the requested stay in the page's own date style ("Jan 27 – Feb 1, 2027 (5 nights)") and up
to 15 whole cards ("Jan 31 – Feb 2 | 2 nights | From € 184"). "unavailable" at confidence 0.8 or
more returns `PriceExecutionStatus.UNAVAILABLE`, which `execute` passes through and the monitor
maps to `no_equivalent_offer` with the detail "The property shows no availability for these dates."
The call goes through the same metered decider, so it counts toward the Jev cap (FR-3).

A first wording that sent de-duplicated lines and ISO dates got "available" at 0.19 on Kalipè's
page; whole cards and the page's date style fixed it (see test walkthrough).
