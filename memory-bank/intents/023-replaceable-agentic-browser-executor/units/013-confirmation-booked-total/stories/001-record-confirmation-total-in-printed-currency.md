---
id: 001-record-confirmation-total-in-printed-currency
unit: 013-confirmation-booked-total
intent: 023-replaceable-agentic-browser-executor
status: complete
priority: must
created: "2026-10-10T01:59:26Z"
assigned_bolt: 092-confirmation-booked-total
implemented: true
---

# US-226: Record the confirmation total in its printed currency

As a user, I want my booking saved with the price and currency Booking.com shows on my confirmation, whatever the currency.

## Acceptance criteria

- The reader accepts the recognized currency symbols and ISO codes printed before an amount and
  reports that currency; euro pages keep producing exactly their current facts.
- Amounts use en-US grouping only; any other grouping or an unrecognized currency token leaves the
  total unknown. A bare dollar sign is not read as any currency;
  dollar currencies need their prefix or ISO code (amended 2026-10-12 from the real page, which
  prints `US$`).
- The room row, the VAT or TAX percentage row, city-tax rows, additional-charge rows and the final
  total must all be in the total's currency and reconcile exactly; otherwise the total is unknown.
- When the page prints no final-price statement, the total must be closed by the
  "Additional Info" heading and a reconciled VAT or TAX row must prove it tax-inclusive
  (added 2026-10-12 from the real page).
- Free cancellation is read from the two cost tiers in one currency, or, only when no cost tier is
  rendered, from the single exact "Refund schedule" full-refund-then-no-refund sentence with
  adjacent cut-off moments. Rendered cost tiers always outrank the sentence.
- The existing property-timezone caution applies unchanged to both cancellation sources.
- No amount is converted and no page content is logged.
