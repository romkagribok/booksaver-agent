---
adr: ADR-053
status: accepted
created: "2026-09-23T14:41:37Z"
bolt: 081-remote-login-resume
---

# ADR-053: Resumable remote login attempts

## Context

The launch link was single-use, leaving the page cancelled the attempt, and the deadline was fixed
at creation. Telegram closes or reloads Mini Apps freely, so fetching an emailed verification code
routinely ended the login with "invalid or expired".

## Decision

Keep the link usable by its owner while the attempt is alive, with exactly one valid viewer at a
time; treat leaving as a detachment with a 180-second grace instead of a cancel; slide the deadline
with viewer activity under a 1,800-second ceiling; resume an existing viewer session on reload.
Explicit Cancel, same-user replacement, administrative cancellation, single browser gate, signed
launch-data replay protection and capture rules are unchanged.

## Consequences

Reopening requires the same Telegram user's freshly signed launch data, so a leaked link alone is
still useless. The shared browser may stay reserved up to three extra minutes when a user never
returns, delaying a price check by at most that. A user who waits longer than the grace gets a plain
message and a fresh `/connect`. Physical Telegram behaviour on iOS and Android remains user-observed.
