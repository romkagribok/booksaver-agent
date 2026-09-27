---
stage: domain-model
bolt: 084-jev-price-executor
created: "2026-09-27T17:00:00Z"
status: complete
---

# Jev feasibility — domain model

Jev (TypeSafe System One, pinned `jev-1.13.0`) is text-only and answers typed Choice/Noul
questions; it never generates text. The feasibility question is therefore not "can Jev browse" but
"can every fact the unchanged price validators need be obtained by Jev *choosing* among
BookSaver-built options while BookSaver code parses and checks the values?"

| Concept | Owner | Trust |
|---|---|---|
| Trusted query (property, dates, occupancy, currency) | Booking row (code) | Trusted |
| Entry URL with stay parameters | Code (`_price_entry_url`, shared with baseline) | Trusted |
| Page snapshot (room/rate cards, headings, viewport text) | Fixed code-owned JS | Untrusted content, bounded shape |
| Jev choice (option id + probabilities) | TypeSafe | Untrusted; validated against offered ids |
| Parsed amount / currency / nights | Code | Derived only from the chosen observed line |
| Stay facts (dates, guests, rooms) | Booking.com's own current URL, parsed by code | Observed |
| Validation, equivalence, savings | Existing domain (`validate_price_observation`, `select_offer`, `detect_savings`) | Authority |

Failure is explicit: no room cards after bounded navigation → `no_valid_observation`; provider
error → `provider_failure`; envelope exhaustion → `budget_exhausted`. Nothing becomes "no savings".
