---
id: ADR-066
status: accepted
created: 2026-11-10T02:08:13Z
bolt: 110-jev-classifies-trip-cards
---

# ADR-066: Jev classifies trip cards; code status words are only the outage fallback

## Context

Trip cards were classified by exact English status and car-rental words. A renamed status can let a
trip's count match while an active hotel is left out, and flights or attractions are never
recognised. The owner wants discovery decided by Jev, not fixed wording.

## Decision

Jev classifies each card on a trip page (stay active, completed or cancelled; other booking active or
inactive; not a booking), asked twice with agreement at 0.8. The count check, the cards to open,
completed skips and cancellation claims use Jev's classes; anything unclassified is opened and blocks
count verification. When TypeSafe is unavailable the code words are used.

## Consequences

- Reworded statuses and new booking types need no code change.
- Two Jev calls per trip page.
- A cancelled card still needs its page's cancellation sentence (a later release may move that to Jev).

## Alternatives

More word lists: the same maintenance problem.
