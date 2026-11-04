---
intent: 030-jev-only-booksaver
phase: inception
status: construction
created: "2026-11-04T15:34:52Z"
updated: "2026-11-04T15:34:52Z"
---

# Requirements: Jev-only BookSaver

## Intent overview

The owner wants BookSaver to run on Jev alone with near-zero maintenance. Two strands:
1. Unit 1 (this release): Jev is the only reader of a reservation's booked total and refund terms;
   the code reader's price and refund parsing, the comparison and the disagreement notice go.
2. Units 2 to 4 (planned, not yet decomposed): remove Claude and the Anthropic key and the code only
   Claude used, in the three releases agreed on 2026-11-03. Their open decisions (users without
   consent, discovery's model fallback, old spend tables, issue #3) are asked at their inception.

## Evidence for unit 1

- 2026-11-04: the owner's two syncs reported a disagreement. Replay: Jev chose the right sentence
  ("Free cancellation within: 5 months 8 days", 0.99) and class (0.98); the code reader read April 12
  from the cost table. The comparison converted the relative wording with 30-day months and a
  timezone margin to April 10 or 11 and allowed one day. Both readers were right; the comparison code
  was wrong.
- The dad's Kalipè stay stayed unconfirmed: Jev's refund-sentence confidence there was 0.66 to 0.79
  in the measurement and one run fell below the 0.6 bar; a stall notice was sent.
- Owner: "it's a mistake now in the code that caused confusion, more code to maintain and the mistakes
  can happen again ... we can solely use [Jev]".

## Functional requirements (unit 1)

- **FR-1, Jev is the reader.** On every upcoming confirmation page Jev reads the total, the refund
  class and the deadline sentence, asked twice; answers must agree. The code reader no longer parses
  price or cancellation sections; its other facts (identity, dates, room, guests, meal plan) stay.
- **FR-2, layout-independent checks only.** Total: one amount, the largest in its currency in the
  price area, confidence at least 0.6. Refund class: confidence at least 0.6. Deadline sentence:
  confidence at least 0.5; a date in it (or "within ..." with calendar months), at least 14 hours
  ahead and not after check-in.
- **FR-3, exact dates when the page has them.** Dated cancellation-cost lines ("until <date> ...")
  are offered as deadline candidates beside the cancellation sentences.
- **FR-4, Jev's total is authoritative.** An agreed total that passes FR-2 is page-verified: it fills
  or replaces the saved total, as ADR-058 allowed for the code reader. Its source is recorded.
- **FR-5, no comparison, no notice, no label.** The disagreement notice and the "read automatically"
  alert line are removed.
- **FR-6, failure is visible.** If Jev is unavailable or over its cap, saved facts are kept;
  a new or changed reservation stays unconfirmed and the stall message covers it.

## Non-functional requirements

- **Maintenance**: no layout-specific price or refund code remains.
- **Cost**: two Jev calls per upcoming page per sync (about USD 0.0001 each).
- **Privacy**: unchanged; only price-area money lines and cancellation and deadline lines are sent.

## Out of scope (unit 1)

Navigation and the other confirmation facts; the Claude removal (units 2 to 4).
