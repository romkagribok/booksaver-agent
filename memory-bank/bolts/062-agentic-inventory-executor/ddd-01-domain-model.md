---
stage: model
bolt: 062-agentic-inventory-executor
created: 2026-08-31T21:58:00Z
---

# Static Model: Genuine Browser Use Inventory Discovery

## Entities

- **Inventory episode**: One bounded authenticated `/bookings` perception run; seeing a saved stay
  is progress but never proves the episode has discovered all visible positives.
- **Positive identity submission**: A current visible confirmation number and lifecycle scope. It is
  sufficient to preserve a new ineligible reservation when richer evidence is unavailable.
- **Positive fact submission**: Bounded optional property, stay, booking, policy, and occupancy
  evidence associated with an identity already submitted in the same episode.

## Value Objects

- **Discovery completion condition**: The agent has inspected visible upcoming cards within the
  fixed caps and explicitly closes the episode; it is not equivalent to matching caller-owned data.
- **Fact envelope**: A bounded provider string decoded into an allowlisted set of optional facts;
  malformed content is rejected without deleting the identity submission.

## Aggregates

- **Positive discovery aggregate**: Rooted at execution ID and confirmation identity. It merges
  compatible current-run facts, rejects conflicts, and grants no absence or eligibility authority.

## Domain Events

- **Known positive observed**: A caller-owned reservation was re-observed; enumeration continues.
- **Unknown positive discovered**: A visible confirmation absent from caller-owned hints was
  submitted and accepted by BookSaver validation.
- **Optional facts attached**: Compatible visible fields enriched a current-run identity.

## Domain Services

- **Browser Use enumeration**: Navigates visible upcoming cards and read-only details through the
  existing guarded tool registry and hard limits.
- **Positive fact merger**: Associates optional evidence only with a current-run confirmation and
  leaves malformed or conflicting facts untrusted.

## Repository Interfaces

- Existing account reservation reconciliation persists accepted positives; no new repository or
  absence authority is introduced.

## Ubiquitous Language

- **Re-observation**: Current evidence for a reservation already stored locally.
- **Discovery**: Current evidence for a Booking.com reservation not stored locally before the run.
- **Cached-row shortcut**: The invalid behavior that treated one saved re-observation as completion.
