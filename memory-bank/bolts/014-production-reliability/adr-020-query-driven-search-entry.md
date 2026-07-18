# ADR-020: Query-driven entry preserves the verified customer search

- **Status**: accepted
- **Date**: 2026-07-18
- **Bolt**: 014-production-reliability (production-reliability)
- **Amends**: ADR-013 search-entry sequence

## Context

ADR-013 replaced the existing-reservation manage page with a complete customer search and required
every check to operate Booking.com's homepage form before navigating through results to the property
room table. That decision correctly established fresh bookable room offers as the sole live-price
source, but production traces exposed a defect in its entry sequence.

On Booking.com's VPS-rendered homepage, calendar selectors drifted and the guarded LLM spent almost
the entire shared check budget trying to repair a form whose values were not used for navigation. The
following step already generated a Booking.com `searchresults.html` query from the same persisted
property, dates, and occupancy. That query successfully rendered results and located the exact hotel,
but it occurred after 348 of 360 seconds had been consumed, leaving no useful recovery budget for the
property page where prices and availability actually appear.

## Decision

1. Every check enters Booking.com's customer search through a `searchresults.html` URL constructed
   solely from persisted property name, check-in/check-out dates, adults, children, and rooms.
2. The active journey does not open, fill, recover, or submit the Booking.com homepage form.
3. Query-driven entry is not a direct-property deep link. The journey must still load Booking.com's
   results, locate the exact property card, open the fresh property href returned by that search,
   verify dates and occupancy, and read the property room/rate view.
4. Result-card headline prices are never a live-price source. Equivalent refundable offers still
   come only from the verified property room/rate content and pass the existing selection and savings
   gates.
5. The guarded, tiered-observation LLM remains available when results, property navigation, context,
   room-view, or offer interpretation differs from scripted expectations. ADR-015 through ADR-017
   remain unchanged.
6. Historical `JourneyStep` enum values may remain for persisted trace compatibility, but inactive
   homepage steps do not appear in new check traces.

## Alternatives considered

- **Keep homepage form recovery first, with a shorter local timeout**: still pays LLM cost for state
  discarded by the next navigation and introduces another budget layer. Rejected.
- **Use the registered property URL directly**: avoids results but weakens the fresh-search path and
  can render a different/session-incomplete rate view. Still rejected as in ADR-013.
- **Use the result-card price**: fast but cannot prove equivalent room type, refundability, or total
  charges. Rejected because it could create non-actionable savings.
- **Increase the global timeout again**: masks redundant work and raises recurring cost without
  improving the price-bearing page interpretation. Rejected.

## Consequences

- Checks reserve their time and LLM-call budget for downstream pages where availability, room type,
  refundability, and prices are actually determined.
- Homepage calendar/autocomplete/occupancy layout drift no longer affects monitoring.
- Booking.com results URL behavior becomes an explicit integration assumption; exact property and
  context verification plus fail-closed outcomes contain that risk.
- ADR-013 remains authoritative for replacing the manage page and requiring results-to-property-to-
  room-table verification, but its homepage form-entry requirement is superseded by this decision.
