---
intent: 015-authentication-boundary-hardening
phase: inception
status: complete
created: 2026-07-26T19:41:07.000Z
updated: 2026-07-26T19:41:07.000Z
---

# Requirements: Authentication Boundary Hardening

## Intent Overview

Make owner-confirmed user purge truthful across both SQLite and encrypted Booking.com session
storage, and constrain the Telegram remote-auth browser to direct Booking.com authentication instead
of unsupported third-party identity-provider sign-in.

## Business Goals

| Goal | Success Metric | Priority |
|------|----------------|----------|
| Make offboarding complete | A successful purge leaves no target-owned database rows, encrypted Booking.com session, or active login capable of restoring one | Must |
| Keep remote login predictable | Google, Apple, and every other external provider page is blocked while direct Booking.com login remains usable | Must |
| Explain the supported path | Telegram and the viewer tell users to use Booking.com email/password without asking for credentials in chat | Must |

## Functional Requirements

### FR-1: Purge all user-scoped authentication data
- **Description**: An owner-confirmed purge must cancel the target's in-flight remote login, remove
  the target's encrypted Booking.com session, establish a permanent local-user revocation marker,
  and only then delete the user and their database-scoped data.
- **Acceptance Criteria**:
  - Typed and inline-confirmation purge paths perform the same cleanup.
  - A matching non-terminal remote-auth attempt is cancelled before session deletion.
  - A successful remote-auth result racing with purge cannot recreate the target session after the
    purge boundary is established.
  - An operator cookie import that validated the target before purge cannot write a session after
    the purge boundary is established.
  - The target session is deleted without touching another user's encrypted session.
  - Session deletion failure prevents database purge and produces a safe failure message rather than
    claiming completion.
  - Database cleanup failure after revocation reports the durable revoked state and directs the
    owner to retry the same confirmed purge.
  - Existing owner protection and explicit confirmation remain mandatory.
- **Priority**: Must
- **Related Stories**: US-097, US-098

### FR-2: Restrict interactive login to Booking.com
- **Description**: The transient remote-auth browser must allow Booking.com document navigation and
  block main-page, child-frame, or popup navigation to every external identity provider.
- **Acceptance Criteria**:
  - Exact `booking.com` and its subdomains remain allowed.
  - Google, Apple, Microsoft, Facebook, arbitrary external hosts, and spoofed Booking hostnames are
    blocked with `blockedbyclient`.
  - The policy applies to the initial page, subsequent same-tab navigation, child frames, and popup
    pages.
  - Cross-origin non-navigation subresources required by Booking.com remain available; this intent
    does not turn the browser into a Booking-only network sandbox.
  - Direct Booking.com email/password and Booking-owned verification flows remain available.
- **Priority**: Must
- **Related Stories**: US-099

### FR-3: Explain direct-login-only behavior
- **Description**: Before and during `/connect`, tell users that they must sign in directly with
  Booking.com credentials and that external providers are disabled.
- **Acceptance Criteria**:
  - The Telegram launch message names direct Booking.com email/password as the supported path.
  - The ready/connected viewer status repeats that Google, Apple, and other providers are disabled.
  - Guidance continues to state that BookSaver never asks for passwords in Telegram chat.
  - Messages reveal no token, cookie, session path, or internal topology.
- **Priority**: Must
- **Related Stories**: US-100

## Non-Functional Requirements

### Security

- Purge ordering must fail closed: cancel capture, delete the encrypted session, then remove SQLite
  state.
- Remote-auth cancellation must share the manager lock used for successful session capture.
- Permanent purge revocation and every encrypted-session save must share the per-owner filesystem
  lock.
- Host checks must use exact-host/subdomain boundaries and reject lookalike domains.

### Reliability

- Purge remains safe when no session or active login exists and can be retried after a storage
  failure.
- Permanent revocation is idempotent so database cleanup can be retried after a cross-store partial
  failure.
- Browser blocking must be installed before the first page is opened and automatically cover popup
  pages.
- Existing timeout, cancellation, session encryption, and browser teardown behavior remains intact.

### Verification

- Unit tests must cover capture-versus-purge ordering, missing and failing session deletion, both
  admin confirmation paths, host-boundary navigation, provider blocking, and user guidance.
- The targeted suites and full repository quality gate must pass.
- Production acceptance requires direct Booking.com login through a real Telegram `/connect`.

## Constraints

- No attempt to bypass Google or another provider's automated/embedded-browser controls.
- No Booking.com native-app automation, credential collection in Telegram, or password storage.
- No database schema or configuration change is required; purge creates a non-secret local
  revocation marker beside encrypted session storage.
- Commit, push, merge, and deployment require separate explicit approval after review.

## Assumptions and Decisions

- The product owner confirmed direct Booking.com login already succeeds in the Telegram viewer.
- External-provider buttons may remain present in Booking.com's third-party page layout, but their
  main-page, child-frame, and popup navigation is disabled and the supported path is stated before
  interaction.
- A filesystem deletion and SQLite commit cannot be one atomic transaction; deleting the session
  before database records prefers retained/retryable user state over a false successful purge.
- The explicit instruction to fix both defects supplies inception and construction authorization
  through test; Git and deployment actions remain held.

## Scope Exclusions

- Making Google, Apple, or other federated login work through BookSaver.
- Hiding provider buttons with layout-specific Booking.com selectors.
- Deleting the owner, changing invite/access policy, or changing ordinary revoke semantics.
