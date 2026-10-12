---
unit: 013-confirmation-booked-total
bolt: 092-confirmation-booked-total
stage: design
status: accepted
created: 2026-10-10T02:00:57Z
updated: 2026-10-12T22:12:52Z
---

# Technical Design - Confirmation Booked Total

## Architecture Pattern

Unchanged: single process, stdlib-first, explicit domain types. The confirmation reader stays a
pure text module behind the grouped reader; persistence authority stays in the SQLite
reconciliation transaction. No new module, service, dependency, route, config key or schema
migration.

## Layer Structure

1. **Infrastructure / confirmation facts reader** (pure, no browser or persistence access)
   - One money pattern: a recognized currency token, optional space, an en-US amount. Tokens are
     a fixed symbol table mapped to ISO codes, or a fixed list of ISO codes Booking.com prints.
     Longer symbols are matched before the bare dollar sign.
   - Price section: same strict position rules as today. The total line fixes the currency; the
     room row, the percentage row labelled VAT or TAX, the per-person city-tax row and the
     additional-charge variant must each be in that currency and reconcile exactly as today.
     The reported currency is the printed one instead of a constant.
   - Unreconciled-row guard: any line holding money plus a tax, fee or charge word outside the
     recognized rows still invalidates the total, now for every currency.
   - Cancellation: cost tiers accept money in one shared currency. When no cost tier line is
     rendered, one line labelled "Refund schedule" followed by the exact full-refund-before /
     not-eligible-after sentence supplies the window. Both sources feed the same existing
     adjacency and property-timezone caution rules.
   - Reasons: the parse entry point takes an optional mapping that receives one fixed reason code
     for an unknown total and one for unknown refundability. Existing callers are unaffected.
2. **Infrastructure / grouped reader and runtime adapter**
   - The grouped reader passes a reasons mapping and adds its codes to counters in the existing
     content-free coverage diagnostic. Nothing else about traversal changes.
   - The runtime adapter marks a reservation's total page-verified only for grouped-reader results
     whose total is present with explicit all-in evidence.
3. **Domain**
   - Observed reservation and reservation observation each gain a page-verified total marker,
     default false. Provider payload models have no such field, so provider output cannot set it.
4. **Application**
   - Merging two observations keeps the marker only when both sides carry it. Mapping to a
     reservation observation keeps it only with explicit all-in evidence.
5. **Persistence**
   - The saved-fact conflict check skips the amount and currency comparison only for a
     page-verified total. The merge then takes the page-verified total instead of the saved one.
   - The existing projection update already rewrites the monitoring baseline and deletes that
     booking's savings opportunities when any projected fact changes; no new statement is needed.

## API Design

No external API. Internal signatures change only by one optional keyword argument on the parse
entry point and one defaulted boolean on two frozen dataclasses.

## Data Model

No schema change. Columns already hold amount and currency text per reservation and per booking.

## Security Design

- Provider output remains untrusted: it cannot mark a total page-verified, so the fail-closed
  conflict rule still protects every saved total from model error or prompt injection.
- Reason codes are a closed set of identifiers with no page text, amount, name or confirmation
  number, consistent with the existing diagnostic and logging boundary.
- Per-caller isolation is unchanged: replacement applies only to the same caller and the same
  confirmation identity inside the caller-scoped transaction.

## NFR Implementation

- **Safety / fail closed**: every new acceptance is a strict full match; anything unexpected
  leaves the fact unknown, exactly as today.
- **No conversion**: the printed currency is recorded and price checks keep requiring it.
- **Reliability**: euro pages must produce byte-identical facts; the existing reader tests are the
  regression guard.
- **Cost / performance**: no extra navigation, model call or action.

## Assumptions to be qualified, not accepted

- On the qualified en-US pages a bare dollar sign means US dollars and other dollar currencies
  carry a prefix or code. If wrong, a non-US dollar reservation would be recorded as USD.
- The dollar confirmation layout is known from a cropped screenshot showing the refund schedule
  sentence, the room row, the "12 % TAX" row and the price row. The lines under "Price" (guest
  count line, total line, final-price statement) are assumed to match the euro layout. If they
  differ the total stays unknown and the reason code will say which rule stopped it.

## Validation plan

- Reader unit tests: dollar layout, several other currencies, grouped thousands, mixed and
  unrecognized currency, comma decimals, each refund schedule rejection, tier precedence, expiry.
- Runtime test: grouped result with a reconciled total is marked page-verified; one without is not.
- Persistence tests: page-verified replacement updates reservation and booking; the same change
  without the marker fails with a persistence conflict and changes nothing.
- Full suite, Ruff, mypy and the AI-DLC validators.
- Affected-caller isolated replay with the existing operator probe pattern (cloned state,
  notifications disabled). It touches the production host and needs separate owner approval.

## Known interaction

Another session's worktree (`meal-plan-equivalence`) holds uncommitted edits to the same reader,
domain, executor and store files. This bolt does not touch that worktree; whichever lands second
will need a rebase and a rerun of these tests.

## Amendment 2026-10-12T22:12:52Z - observed dollar layout

The affected caller's real confirmation page was replayed and its price block captured once.
It differs from the assumptions above in two ways, and the design follows the evidence:

1. **No final-price statement.** The block is `Price`, `(for 2 guests)`, the total, then the
   heading `Additional Info`. The reader therefore accepts a second closed shape: when no
   final-price statement is rendered anywhere, the line after the total must be exactly
   `Additional Info`. Because the statement was the page's own assurance that the total is final,
   this shape additionally requires a reconciled VAT or TAX percentage row, which proves the
   total is tax-inclusive. Without that row the total stays unknown with reason
   `tax_inclusion_unproven`. Every other rule (single room row, exact sum, single currency,
   charge-warning scan, unreconciled-row scan) applies unchanged.
2. **Prefixed dollars.** The page prints `US$309`, not `$309`. The bare dollar sign is removed
   from the symbol table: it was an unobserved assumption with a real failure mode (another
   dollar currency recorded as USD). Only prefixed symbols and ISO codes are read.

The refund schedule label is on its own line followed by the sentence, which the design already
accepted and the replay confirmed.
