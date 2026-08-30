---
stage: model
bolt: 061-agentic-inventory-executor
created: 2026-08-30T22:29:00Z
---

# Static Model: Canonical HTTPS Browser Use Inventory Entry

## Entities

- **Bookings inventory execution**: The existing bounded `/bookings` execution; its domain
  authority, session lease, limits, and positive-only result are unchanged.
- **Code-owned inventory entry**: A fixed adapter-specific HTTPS Booking.com destination selected
  before untrusted agent perception begins.

## Value Objects

- **Canonical Browser Use inventory URL**: `https://secure.booking.com/mytrips.html`; it contains
  no credentials, query, fragment, mutable action, or model-provided component.
- **Legacy redirect**: The observed HTTP `mytrips` redirect from the old `myreservations` entry;
  it remains prohibited egress and cannot grant authority by being provider-generated.
- **Safe popup link**: A visible inspected Booking.com anchor whose HTTPS destination passes the
  existing deny-oriented guard but whose presentation requests a new tab.
- **Structural ancestor**: A non-interactive DOM ancestor whose meaningful text is aggregate page
  content rather than the label of the clicked control.
- **Rejected click proposal**: An untrusted model request denied before physical replay; it consumes
  the bounded action allowance but does not become a safety incident or terminate the episode by
  itself.

## Aggregates

- **Bookings execution aggregate**: Owns the fixed entry, authenticated browser, agent episode,
  and teardown. Navigation failure closes the aggregate without fallback or domain mutation.

## Domain Events

- **Canonical inventory entered**: The transient browser reaches an HTTPS Booking.com inventory
  page and may begin untrusted perception.
- **Insecure redirect denied**: An HTTP request remains blocked by the egress guard.

## Domain Services

- **Trigger-specific entry selector**: Browser Use `/bookings` receives canonical `mytrips`; the
  Stagehand adapter and all other triggers keep their established route.
- **Same-tab link normalizer**: Converts only an already-guarded safe popup link into same-tab
  navigation, preserving one target and all pre- and post-destination checks.
- **Interactive-chain guard**: Inspects the clicked node and interactive ancestors for labels while
  retaining role, attribute, event-handler, target, and destination checks on every ancestor.
- **Bounded correction loop**: Returns one successful content-free guard outcome after a
  pre-action rejection so Browser Use may select another inventory control without incrementing
  harness failure recovery; the request still consumes BookSaver's unchanged action limit.
- **Egress guard**: Continues to permit only approved HTTPS Booking/static and loopback traffic.

## Repository Interfaces

- None. This correction changes no persisted state or contract.

## Ubiquitous Language

- **Direct HTTPS entry**: Code chooses the current protected route without following an insecure
  compatibility redirect.
- **No redirect exception**: Provider behavior does not weaken the transport policy.
