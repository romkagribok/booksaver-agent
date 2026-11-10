---
stage: implement
bolt: 110-jev-classifies-trip-cards
created: 2026-11-10T02:21:59Z
---

# Implementation Walkthrough

- `JevReservationFacts.classify_cards`: one six-class question per card (lines through `_safe`, at
  most eight), empty state, two parallel asks, `_agreed` at 0.8; None on budget stop or failure;
  counted as `cards_classified` / `cards_unavailable` in the sync's Jev run diagnostic.
- `GroupedInventoryReader.cards` merges reservation links per canonical key and keeps other
  multi-line links (at most 30); `card_classes` maps classes to keys and drops a "stay" class on a
  non-reservation link. In `run`, classes drive the count check (every card classified; count equals
  stays or active stays plus active other bookings), the targets (stays when the count is verified,
  otherwise every reservation link), completed skips and cancellation claims; with no classes the
  previous code path runs unchanged. The executor passes `assist.classify_cards`.
- The count wait loop still uses the code check only to wait for rendering (bounded, harmless).
