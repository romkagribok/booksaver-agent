---
adr: ADR-025
status: accepted
created: 2026-07-19T21:23:00Z
bolt: 025-authenticated-mobile-web-monitoring
amends: ADR-007, ADR-013, ADR-020
depends_on: ADR-024
---

# ADR-025: Authenticated Mobile Web Is the Primary Price Context

## Context

Desktop/public checks can miss logged-in Genius and mobile-web rates. Mobile layout also changes the
DOM that scripted and LLM recovery paths observe.

## Decision

For Telegram-owned monitoring, use one allowlisted Android-like Chromium Playwright device profile
with the booking owner's validated per-user session. Accept a price only with complete redacted
provenance: authenticated mobile-web channel, profile, session revision, authentication validation,
Genius evidence tri-state, and timestamp. Preserve ADR-013/020's trusted journey and equivalence gates
and all browser-agent action/cost guards.

## Consequences

- Mobile-web/account-eligible rates become the explicit monitored source.
- Auth or pricing ambiguity fails closed instead of silently returning public prices.
- Mobile DOM fixtures and provenance storage increase test/schema scope.
- Native Booking.com app/app-only promotions remain unsupported; final action stays on the real phone.
