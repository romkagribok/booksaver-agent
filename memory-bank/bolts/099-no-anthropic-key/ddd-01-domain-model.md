---
unit: 002-no-anthropic-key
bolt: 099-no-anthropic-key
stage: model
status: complete
created: 2026-11-06T00:27:55Z
updated: 2026-11-06T00:27:55Z
---

# Static Model - No Anthropic Key

## Bounded Context

Which method serves each user, what invitees are told, and what account sync does when its code
reader cannot read a trip list.

## Domain Entities

- **User**: owner or invitee. Every active user is served by Jev and the code reader.
- **Disclosure record**: the latest disclosure version a user accepted or was informed of.

## Domain Rules

1. Routing no longer depends on the disclosure record.
2. An invitee with a session is informed once that TypeSafe's Jev reads page content; the record is
   set to the current version so it is never repeated and `/connect` does not ask again.
3. A trip list the code reader cannot read fails the sync visibly; no model navigates.
4. No component requires `BOOKSAVER_LLM_API_KEY`.
