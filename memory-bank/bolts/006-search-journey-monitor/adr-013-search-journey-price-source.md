# ADR-013: Full search journey replaces the manage page as the sole price source

- **Status**: accepted
- **Date**: 2026-07-05
- **Bolt**: 006-search-journey-monitor (search-journey-monitor)

## Context

The MVP monitor (bolt 003) opens `secure.booking.com/myreservations.html` and extracts a
"current price" from it. Booking.com does not re-quote an existing reservation there — the
page shows what was already paid, so that check cannot surface a real cancel-and-rebook
saving. Real savings appear only when the same property and dates are searched again as a
new customer and a cheaper equivalent refundable offer shows up.

Two navigation strategies were considered for reaching the property's room table:
deep-linking the property URL with `checkin/checkout/group_adults` query params, or
replicating the complete user search journey (home → search box → results → property page).

## Decision

The **full search journey is the sole producer of live prices** (user decision at intent-002
Checkpoint 1, deliberately choosing the journey over deep-linking):

1. Every check runs home → dismiss overlays → fill search (property name, exact dates,
   real occupancy) → submit → locate + verify property in results → open property page →
   verify dates/occupancy → read room table. No deep-link shortcut, not even as fallback.
2. The manage page is retired as a price source. Session validation keeps using page
   sign-in markers; nothing navigates to `myreservations.html` during checks.
3. The journey is decomposed into named steps (`JourneyStep` enum), each with a reportable
   outcome — these seams are where bolt 007 attaches LLM-agent escalation.

## Alternatives considered

- **Deep-link property URL with date/occupancy params**: fewer steps, fewer failure modes,
  but bypasses search-results pricing and may miss session-tied member/Genius rates or
  render a different rate view than a searching customer sees. Rejected by user decision:
  the monitor must see exactly what a rebooking customer would see.
- **Keep manage-page check as fallback price source**: rejected — its "price" is not a
  bookable quote; a fallback that can emit non-actionable numbers is worse than a coded
  failure.

## Consequences

- More journey steps = more drift surface; mitigated by per-step failure codes
  (`STEP_FAILED` naming the step) and bolt 007's agent escalation at those seams.
- New failure vocabulary (`PROPERTY_NOT_FOUND`, `NO_EQUIVALENT_OFFER`, `BOT_WALL`) makes
  non-actionable outcomes diagnosable instead of fabricating prices.
- Bot-detection exposure rises (search flows are more instrumented than account pages);
  `BOT_WALL` is recorded distinctly and feeds the existing failure tracker/backoff.
- The savings gate's semantics are preserved by verifying property/dates upstream and
  emitting only non-contradicting extracted fields (see ddd-01 mapping rules).
