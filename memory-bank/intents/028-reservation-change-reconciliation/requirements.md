---
intent: 028-reservation-change-reconciliation
phase: inception
status: units-defined
created: "2026-11-02T20:51:19Z"
updated: "2026-11-02T20:51:19Z"
---

# Requirements: Reservation change reconciliation

## Intent overview

The owner moved a reservation to new dates in Booking.com under the same confirmation number.
Intent 019 FR-5 requires such a change to update the same reservation. Account synchronization
instead fails every run with `persistence_conflict`, so the booking has had no price check since
2026-10-26 and nobody was told. The last six checks before that failed with `currency_mismatch`,
also silently.

## Evidence (live probes on cloned state, 2026-11-02, kit `rescheck-20261102`)

- The reader reads the new stay correctly with no model call: 2027-04-15 to 2027-04-16, refund
  deadline 2027-04-12, same room and occupancy. Conflicts: `check_in`, `check_out`,
  `refund_deadline`.
- The price section prints `approx. € 591` between `(for 2 guests)` and `US$659.68`, so the reader
  stops with `final_price_statement` and leaves the total unknown.
- Booking.com redirects the signed-in property page and drops `selected_currency`; adding
  `changed_currency=1` does not help. Signed in shows euros, signed out shows dollars.
- Re-opening the redirected URL with `selected_currency=USD` shows only dollars and survives a
  reload. Later visits without the parameter return to euros, so it is needed on each check.
- The cause of the switch on 2026-10-24 was not established and is not needed for the fix.

## Business goals

| Goal | Success metric | Priority |
|------|----------------|----------|
| A changed reservation keeps being monitored | Owner's booking verifies a price on its new dates after release, with no manual step | Must |
| No false saving after a change | No savings alert compares against a total from before the change | Must |
| Stalled monitoring is visible | An affected user is told within one scheduled run of 24 hours passing | Must |

## Functional requirements

- **FR-1, accept code-read changes.** When a code-owned reader observes a reservation with the same
  confirmation number and the same recognized hotel, differing check-in, check-out, refund deadline,
  refundability, room or occupancy update that reservation and its monitored booking. Both stay
  dates must be present in the observation. Provider-submitted facts keep failing closed; the
  property identity rule of ADR-058 and the lifecycle rules are unchanged.
- **FR-2, no stale facts.** When the stay dates, room or occupancy change, any fact that depends on
  the old stay and was not re-read in that observation (booked total, refundability, refund deadline, refund note)
  is cleared, never carried over.
- **FR-3, read the total under a converted breakdown.** When the session displays another currency,
  the page prints `1 room` and tax rows and `approx. <amount>` in that currency, followed by the
  total in the booked currency and `Additional Info`. The reader records that total only when the
  conversion line is directly above it in a different currency, the rows are all in the conversion's
  currency and include a percentage tax row that matches the room row, and the rows sum to the
  conversion. Whole-unit display rounding of at most 1 is allowed in these converted rows only. Any
  other shape stays unknown. BookSaver stores the printed booked-currency total and never converts.
- **FR-4, hold while the total is unknown.** A reservation without a verified total is ineligible
  (existing `MISSING_BOOKED_TOTAL`), its saved opportunities are removed and it can produce no
  savings alert. It is monitored again automatically once a later sync verifies the total.
- **FR-5, invalidate old savings.** Any change under FR-1 removes the booking's saved opportunities
  in the same transaction. Check history is kept.
- **FR-6, keep the Jev page in the booked currency.** When Booking.com's redirect drops
  `selected_currency`, the Jev price method re-opens the redirected page once with the booking's
  currency before reading offers, and an error-page reload keeps it. Host and safety invariants are
  re-checked. A page still in another currency keeps failing with `currency_mismatch`.
- **FR-7, stall notice.** After a scheduled run, if a monitored upcoming reservation has had no
  conclusive price result for 24 hours, its own user gets one Telegram message naming the reason in
  plain words. Reasons: sync failing, total unconfirmed, price checks failing. A conclusive result is
  a verified price or a verified "no equivalent offer".
- **FR-8, recovery and repeats.** One further message is sent when that reservation next gets a
  conclusive result. No repeat during one stall, including across daemon restarts. No stall notice
  while the session already has a sign-in or uncertain-session notice. Messages stay per-user and
  contain no other user's data.

## Non-functional requirements

- **Privacy**: ordinary logs keep field names and reason codes only.
- **Cost**: at most one extra page load per check; no model call added.
- **Atomicity**: FR-1, FR-2 and FR-5 commit in the existing per-user sync transaction.
- **Compatibility**: invitee reservations whose facts did not change see no behaviour change.

## Out of scope

- The Claude price methods and scripted paths: dormant, and due for removal under a later intent.
- Finding why the account default changed to euros.
- Removing Anthropic or any other Jev-only cleanup; that is the next intent.
- A new-confirmation rebook: already handled as a separate reservation (019 FR-5).

## Amendments

### 2026-11-03T00:49:01Z: rows above `Price` captured (kit `rescheck-20261102`, probe 4)

Inception assumed the rows above `Price` might reconcile in the total's currency. The capture shows
`1 room € 526`, `12 % TAX € 63`, `approx. € 589`, `US$659.68`. FR-3 is rewritten to that observed
shape, as inception's open item foresaw. FR-2 also covers room and occupancy changes, because either
can change the total. The owner approved the requirements and plan with no price checks during a
hold, and approved commit, merge and deploy if nothing unexpected arises. Recorded here as an
anticipated design change, reported to the owner.
