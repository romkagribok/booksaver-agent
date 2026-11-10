---
stage: plan
bolt: 110-jev-classifies-trip-cards
created: 2026-11-10T02:08:13Z
---

# Implementation Plan

- `JevReservationFacts.classify_cards(cards)`: one question per card (six classes), personal lines
  removed, asked twice in parallel, agreement at 0.8; returns None when Jev is unavailable or over
  budget. It counts toward the sync's Jev spend like confirmation pages.
- `GroupedInventoryReader`: `cards(snapshot)` merges reservation links per booking and keeps other
  multi-line links; `classify` callback (the executor passes `assist.classify_cards`). With classes:
  count check, targets, completed skips and cancellation claims use them; without: today's code.
- Unit tests with the captured trip-page shapes; offline Jev check on the captured cards plus
  renamed-status, flight and attraction variants; staged replay of users 4, 1 and 3.
