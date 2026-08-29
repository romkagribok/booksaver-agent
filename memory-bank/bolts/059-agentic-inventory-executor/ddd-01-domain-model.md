---
stage: model
bolt: 059-agentic-inventory-executor
created: 2026-08-29T20:51:44Z
---

# Static Model: Mobile Session Identity and Navigation Failure

## Entities

- **Agentic browser execution**: Owns one transient browser, one owner-bound session lease, one
  configured browser identity, and bounded navigation/perception work. It cannot begin perception
  until trusted navigation reaches a real Booking.com document.
- **Authenticated session snapshot**: Encrypted owner-bound cookies captured and verified under an
  accepted mobile-web identity family. Cookie material remains opaque outside the browser bootstrap.
- **Navigation attempt**: One code-owned top-level transition with a requested Booking.com
  capability, sanitized transport outcome, and final destination classification.

## Value Objects

- **Mobile browser identity**: Version-matched Playwright profile ID, user agent, viewport, device
  scale, touch capability, and locale derived from trusted configuration. It contains no session or
  account values.
- **Navigation failure category**: Closed values for redirect loop, timeout, connection failure,
  certificate failure, generic browser transport failure, and unknown failure.
- **Protected capability**: Code-owned inventory or price entry target whose successful document
  load is a prerequisite for model perception, not evidence of domain correctness.

## Aggregates

- **Transient browser aggregate**: Rooted at the agentic execution; browser identity is fixed before
  cookie restoration and cannot change during the lease. Navigation failure closes the attempt
  before Stagehand extraction or computer use.
- **Inventory execution result**: Maps an authentication redirect loop at its fixed protected entry
  to signed-out; other transport failures remain fail-closed provider outcomes. No browser failure
  acquires destination or interaction authority.

## Domain Events

- **Protected capability reached**: A real HTTPS Booking.com document is available for guarded
  semantic perception.
- **Navigation failed**: A content-free closed transport category terminates the attempt with zero
  model usage.
- **Authentication redirect loop detected**: The inventory capability could not be reached under
  the restored session and requires an authentication outcome rather than a safety violation.

## Domain Services

- **Browser identity resolver**: Converts the configured allowlisted mobile profile into exact,
  version-matched launch properties.
- **Navigation failure classifier**: Converts browser transport evidence into a closed category;
  it never retains raw URLs, redirect values, page content, cookies, or account data.
- **Inventory terminal mapper**: Maps the fixed-entry redirect loop to signed-out and all other
  transport categories to fail-closed provider failure.

## Repository Interfaces

- No new repository is required. Existing content-free execution metrics retain only the resulting
  terminal code, usage, cost, and latency.

## Ubiquitous Language

- **Session identity affinity**: Restoring session cookies only into the supported mobile browser
  identity family in which BookSaver captures and verifies them.
- **Capability reachability**: Successful loading of the requested protected resource before model
  perception; it is not DOM authentication verification or domain evidence.
- **Internal browser error page**: A Chromium-owned failure document that is never a Booking.com
  destination and never model-visible evidence.
- **Robustness**: Preserve provider/session compatibility and typed failure causality rather than
  adding selectors or broadening model authority.
