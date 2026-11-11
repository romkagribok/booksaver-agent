---
stage: plan
bolt: 113-legible-reports
created: 2026-11-11T00:11:18Z
---

# Implementation Plan

## Objective

Read ended free cancellation (US-265) and put every user report into plain words (US-266, US-267).

## Deliverables

- `jev_reservation_facts.check_refund`: a passed deadline gives `explicit_nonrefundable` with
  "Free cancellation ended on <d Mon yyyy>."
- New `infrastructure/telegram/plain_text.py`, shared by every reply: `day`, `stay`, `moment`,
  `versus_paid` and `failure_text` (one sentence per `FailureCode`, with a fallback).
- `commands_readonly.py`:
  - `/bookings`: the stay with `stay`, a free-cancellation line, and the two reason labels.
  - `/savings`: hotel, stay, price paid and price found, the saving, and when it was found.
  - `/checks`: a header with the hotel, stay and price paid; plain lines with no profile.
- `check_now.py`: a plain completion, plus the alert minimum when the saving is under 5.
- `savings_pipeline.render_alert`: "Checked as" and Genius lines in plain words.
- Unit tests for each, with existing tests updated to the new wording.

## Technical Approach

Formatting only, plus one branch in `check_refund`. No schema, config or Jev question change.

## Acceptance Criteria

See US-265, US-266 and US-267.
