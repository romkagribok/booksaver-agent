---
id: 001-route-everyone-to-jev
unit: 002-no-anthropic-key
intent: 030-jev-only-booksaver
status: complete
priority: must
created: "2026-11-04T16:13:23Z"
assigned_bolt: 099-no-anthropic-key
implemented: true
---

# US-246: Route every user to Jev

## User story

As an invitee, I want my checks to keep running after the provider changes, so that nothing stops.

## Assigned requirement

FR-7, FR-8.

## Acceptance criteria

- [ ] Given an invitee whose disclosure names Anthropic, when a scheduled run happens, then price checks use Jev and sync uses the code reader with Jev.
- [ ] Given an invitee with a session, when the release runs, then they get one message naming TypeSafe's Jev, and never again.
- [ ] Given a new invite at /connect, when the disclosure shows, then it names TypeSafe.

## Out of scope

Anything outside unit 002-no-anthropic-key.
