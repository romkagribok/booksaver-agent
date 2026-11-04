---
intent: 029-jev-reservation-facts
phase: inception
status: construction
created: "2026-11-03T19:24:37Z"
updated: "2026-11-03T19:24:37Z"
---

# Requirements: Jev-assisted reservation facts

## Intent overview

Account sync reads each reservation's booked total and refund terms with exact code-owned layouts.
Every new Booking.com layout leaves those facts unknown, and the reservation is silently never
monitored. On 2026-11-03 none of the owner's dad's six upcoming stays was monitored; four of them
are refundable. The owner asked for a robust and lean solution that uses Jev in syncs the way price
checks use it, ignoring deadlines.

## Evidence (read-only capture on cloned state, 2026-11-03, kit `dadsync-20261103`)

| Stay | Real terms | Code reader result |
|---|---|---|
| AIRINN, Nov 10 | Non-refundable | refund wording unrecognized |
| Aloft, Nov 11 | Non-refundable | read correctly |
| Hampton, Nov 12-15 | Refundable to Nov 7; US$577.42 under an `approx. € 516` breakdown, then the final-price sentence | total unknown (`converted_price_shape`) |
| Best Western, Nov 12-15 | Refundable to Nov 11; US$521.11, same shape | total unknown |
| AIRINN, Nov 17 | Refundable to Nov 17; €102, `(for 1 guest)` | total unknown (`guest_count_line`) |
| Kalipè, Jan 27 | €701; full refund before Jan 23, then partial | refund wording unrecognized |

In every case the page proves the answer by arithmetic or by explicit wording; only the shape
differs. A sync of this account takes 49 to 163 seconds against a 180-second limit.

## Principle

Jev selects, code proves. Jev never produces a value: it picks lines that code extracted from the
page, and code accepts a pick only when its own checks prove it. Anything unproven stays unknown,
exactly as today. No model-only fact is ever stored.

## Functional requirements

- **FR-1, code first.** The existing code reader runs first and its results stand. Jev is asked only
  about a booked total or refund terms that the code left unknown.
- **FR-2, booked total.** Code extracts the money lines of the price section as options. Jev picks
  the total the guest pays. Code accepts it only when the component rows (room and tax rows) sum to
  it in its currency, or sum to an `approx.` conversion line directly above it in another currency,
  within display rounding of 1 in the converted currency only; a percentage tax row must match its
  room row. The pick must be the only amount in its currency in the price section.
- **FR-3, refund terms.** Code extracts the cancellation and refund sentences as options. Jev picks
  the sentence that states when free cancellation ends, or that the booking is non-refundable.
  Code accepts refundable only when that sentence contains a full-refund or free-cancellation
  phrase and a date that code parses, on or before check-in; that date is the refund deadline.
  Code accepts non-refundable only when the sentence says so explicitly. Otherwise unknown.
- **FR-4, minimal data to TypeSafe.** Only the candidate lines and the question are sent: no guest
  name, address, contact details or confirmation number. Lines are bounded in count and length.
- **FR-5, same trust as code.** A proven fact is stored as page-verified, so ADR-059 applies to it
  unchanged. The sync diagnostic records which facts Jev filled, by field name only.
- **FR-6, cost.** Jev calls for syncs count toward the existing Jev daily cost cap, at most one
  question set per reservation page per sync. Over the cap, facts stay unknown.
- **FR-7, unreadable stays are visible.** An upcoming reservation that is not monitored only because
  its total or refund terms are unknown counts as stalled after 24 hours, so its user gets the
  existing stall message once. Non-refundable or cancelled reservations never do.
- **FR-8, sync time limit.** The account sync limit rises from 180 to 300 seconds.

## Non-functional requirements

- **Safety**: an unproven pick never becomes a stored fact; failure of Jev or TypeSafe leaves today's
  behaviour.
- **Cost**: about USD 0.001 per assisted page; none when the code reader succeeds.
- **Privacy**: ordinary logs keep field names and reason codes only.

## Out of scope

- Jev for navigation or the rest of discovery (the Claude navigation fallback is for the Jev-only
  cleanup to remove).
- Stay dates, room and occupancy (the code reader reads them on every observed page).
- New code-owned layouts for these shapes: the proofs in FR-2 and FR-3 cover them.

## Owner decision (approved)

- Approved: FR-4 sends reservation-page lines to TypeSafe for the first time; price checks send only hotel
  search pages. The invitees' current disclosure names Anthropic, not TypeSafe (the Jev-only
  cleanup replaces it).

## Amendments

### 2026-11-03T21:56:42Z: construction findings (owner review pending at the commit stop)

- **FR-2 and FR-3, who chooses.** Testing on the six captured pages showed each proof passes on
  exactly one candidate line or sentence. Code therefore tries every candidate and accepts a fact
  only when the page proves exactly one answer. Jev is asked only when the page proves more than
  one different refund term, and is offered only those proven sentences. Totals never go to Jev:
  if two totals were proven, the total stays unknown. Effect: fewer TypeSafe calls and less data
  sent than approved, never more; the safety rule (no fact without code's proof) is unchanged.
- **Charge warnings.** The Hampton page's policy sentence "Special requests cannot be guaranteed and
  may incur additional charges" made both readers treat the total as not all-in. A sentence tying a
  charge that special requests *may* incur is now an optional extra; "mandatory" wording or a plain
  "additional charges apply" still blocks, as the existing tests require.
- **FR-8 timing.** Raising sync to 300 seconds raised the daemon's check-now and scheduled job limit
  from 360 to 480 seconds, so the price phase keeps its 180 seconds.
- **Staging found the owner's own booking unmonitored in production**: the owner rebooked the Union
  Club stay after the 13:40Z alert, and the new confirmation's total (USD 592.48) is in the same
  converted shape. The candidate reads it.
- **2026-11-03T22:19:46Z, Codex review.** The fallback retries only facts the code reader left unknown
  because of the page's layout, never its deliberate rejections (rendered cost tiers, unprovable
  cutoffs, fees, mixed currencies). Refund wording must be an affirmative construction with no
  negation; fee rows outside the breakdown and same-day cutoffs fail proof, as in the code reader.

### 2026-11-04T00:10:38Z: redesign to "Jev reads, code cross-checks" (owner decision)

Codex found nine gaps in five review rounds, all from re-implementing the code reader's
layout-specific safeguards in a parallel proof. The owner's goal is near-zero maintenance ("constantly
updating code on each case is definitely not the move"). Measured on the seven real reservations,
three runs each: Jev chose the right total 21/21 and the right refundability 21/21, consistently; it
was unreliable on whether taxes are included (confidence 0.19 to 0.61, one wrong). The owner chose
the middle ground. **FR-1 to FR-6 are replaced by:**

- **FR-1, Jev reads every upcoming confirmation page:** which line is the total, whether the
  reservation is refundable, and which sentence states its deadline. It is asked twice; both answers
  must agree, each with confidence of at least 0.6. No tax question.
- **FR-2, layout-independent checks:** the chosen total is the largest amount in its currency in the
  price area; a refundable deadline is a date in the chosen sentence, or "within N months/days/hours"
  from the observation time, at least 14 hours ahead and not after check-in.
- **FR-3, code wins where it reads:** a code-read total or refund term stands. Where Jev disagrees,
  code's value is kept, the disagreement is recorded, and the owner gets one content-free Telegram
  notice per UTC day.
- **FR-4, Jev fills what code cannot read**, marked as Jev-read. A Jev total may fill a missing or
  cleared total but never replaces a saved one; a later code-read total replaces a Jev one. Jev never
  causes a sync conflict.
- **FR-5, labelled alerts:** a savings alert whose booked total was Jev-read says the total was read
  automatically and should be checked before rebooking.
- **FR-6, data and cost:** only the price-area money lines and cancellation sentences are sent; Jev
  calls count toward the existing daily cap, with at most two calls per page and 20 per sync.

FR-7 and FR-8 are unchanged. The earlier amendments' code proofs (`prove_total`, refund templates)
are removed; the code reader keeps its exact special-request exemption.

