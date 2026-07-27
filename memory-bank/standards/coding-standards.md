# Coding Standards

## Python Code Standards

- Keep secrets out of git and read credentials from local config only.
- Prefer explicit domain types for synchronized reservations, bookings, prices, check results, savings
  opportunities, and synchronization outcomes.
- Keep account inventory, browser automation, LLM extraction, persistence, savings evaluation, and
  notification delivery separated by module boundaries.
- Add tests with coverage focused on local config validation, caller-scoped persistence invariants,
  completeness-gated reconciliation, savings equivalence rules, and browser safety boundaries.
- Preserve the MVP product constraints: Booking.com hotels only, refundable bookings only, equivalent cheaper offers only, no autonomous cancel or purchase, local-only data.
- Treat Booking.com account inventory as reservation truth. Do not add local booking mutation or
  guided-rebooking paths.
