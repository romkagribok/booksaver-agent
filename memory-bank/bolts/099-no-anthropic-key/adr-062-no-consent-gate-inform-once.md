---
id: ADR-062
status: accepted
created: 2026-11-06T00:27:55Z
bolt: 099-no-anthropic-key
---

# ADR-062: No disclosure gate; invitees are informed once of TypeSafe

## Context

Invitees accepted a disclosure naming Anthropic. Routing used that acceptance to choose between the
Claude-era methods and the legacy scripted path. Changing the disclosure would have silently moved
invitees onto the legacy path. The owner chose (2026-11-04) to keep checking invitees and inform
them once rather than ask them to accept again.

## Decision

Routing no longer depends on the disclosure record: every active user is served by Jev and the code
reader. Each invitee with a session is told once, in Telegram, that TypeSafe's Jev now reads the page
content; the disclosure record is set to the TypeSafe version. New invites see the TypeSafe text at
`/connect`.

## Consequences

- No invitee is ever moved onto a different method without notice; the legacy paths become unused.
- Invitees are informed, not asked; this is weaker consent than an accept step (owner's choice).

## Alternatives

Pause invitees until they accept the new disclosure (recommended earlier; declined by the owner).
