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

## Units 2 to 4: remove Claude (2026-11-04T16:13:23Z)

Owner decisions of 2026-11-04: invitees keep being checked and are informed once (no new accept
step); drop reservation discovery's Claude fallback; drop the Claude spend and qualification tables
after a backup; close issue #3. Start before unit 1's read-back; deploy only after it.

### Unit 2: no Anthropic key needed (release A)

- **FR-7, everyone on Jev.** Every active user's price checks use Jev and account sync uses the
  code reader with Jev, whatever their disclosure record; the scripted price path and the legacy
  inventory source are no longer selected for anyone.
- **FR-8, inform once.** Each invitee with a Booking.com session gets one Telegram message that page
  content is now read by TypeSafe's Jev, not Anthropic; recorded so it is never repeated. New invites
  see the updated disclosure text naming TypeSafe at `/connect`.
- **FR-9, no Claude fallback in discovery.** When the code reader cannot read an account's trip list,
  the sync fails visibly (existing stall message after 24 hours); no model navigates.
- **FR-10, starts without the key.** The daemon, bot and syncs run with `BOOKSAVER_LLM_API_KEY`
  unset; after release the key is removed from the VPS and the owner revokes it at Anthropic.

### Unit 3: delete the Claude code (release B)

- **FR-11.** Remove the Claude price methods (Stagehand and Browser Use agents), the paired
  comparison mode, the scripted price path with its Claude recovery and browser agent, the page-state
  classifier, the model-policy and adaptive-execution layer, the Anthropic adapter and client factory,
  the legacy inventory source, the Stagehand inventory executor, `/setkey` and `/deletekey`, and the
  Claude-only evaluation CLI. Helpers that Jev or the code reader use move to neutral modules first.
  Drop the `stagehand` dependency; `anthropic` stays only as browser-use's own dependency.
- **FR-12.** Behaviour for every user is unchanged from unit 2 (Jev price checks, code reader plus
  Jev syncs); the full suite and a live replay prove it.

### Unit 4: data, config and docs (release C)

- **FR-13.** After a backup, drop `llm_spend_days`, `llm_cost_reservations` and
  `llm_profile_qualifications`; users' stored personal keys are cleared.
- **FR-14.** Old config keys for Claude models and model-call limits are ignored with one warning, so
  existing configs load; they are removed from the example config.
- **FR-15.** README, `AGENTS.md` (secrets list), the example config and the standards name TypeSafe
  as the only model provider. Issues #79 and #3 are closed; #4 and #5 are reviewed.

### Non-functional (units 2 to 4)

- Each release ships and rolls back on its own; unit 3 is a pure deletion with no behaviour change.
- No new dependency; source shrinks substantially (estimated 12,000+ lines, measured in unit 3).

