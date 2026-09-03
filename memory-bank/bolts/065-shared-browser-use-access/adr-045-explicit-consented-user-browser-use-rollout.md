---
id: ADR-045
title: Explicit consented-user Browser Use rollout
status: accepted
created: 2026-09-03T23:39:00Z
bolt: 065-shared-browser-use-access
---

# ADR-045: Explicit Consented-User Browser Use Rollout

## Context

Browser Use now completes the deployment owner's inventory and price workflow, while invited-user
price checks remain on the selector-dependent legacy route until the statistical qualification gate
passes. The deployment currently has no general invitee traffic, and the owner has explicitly chosen
to prioritize the working Browser Use path for invited users rather than continue legacy DOM
maintenance.

The existing route names carry useful meanings: `owner_canary` proves only owner behavior, while
`agentic` represents statistically qualified promotion. Reinterpreting either would make stored
qualification state and operator commands misleading. Silent rollout would also violate the
versioned disclosure boundary for authenticated Booking.com page processing.

## Decision

Add an explicit `consented_users` price-routing mode. It admits the active deployment owner and
every active invited user whose stored disclosure acknowledgement exactly matches the configured
version. It does not require or mutate statistically qualified state. Missing or stale invitee
consent remains a closed `disclosure_required` decision.

Keep `legacy`, `owner_canary`, and qualification-gated `agentic` unchanged. A globally recorded
regression remains stronger than every agentic configuration and routes future price work to
legacy. Existing safety, privacy, authorization, session, validation, action, destination, cost,
timeout, and transaction prohibitions remain binding.

Manual `/checknow` and scheduled work continue resolving through the same coordinator method.
Agentic inventory already uses Browser Use for the owner and currently disclosed invitees and needs
no new route or executor.

Qualification evidence remains a monitoring, comparison, and rollback signal. Selecting
`consented_users` is an explicit risk acceptance by the self-hosting owner, not a claim that the
30-check, 14-day, correctness, reliability, or cost targets passed. Existing automatic regression
evidence is owner-canary scoped; broader invitee-derived regression automation is future work and is
not implied by this rollout.

## Alternatives Considered

- **Reinterpret `owner_canary` to include invitees**: rejected because the name, stored evidence,
  and existing tests intentionally mean owner-only.
- **Reinterpret `agentic` to bypass qualification**: rejected because it would make the promotion
  command and persisted qualification state dishonest.
- **Auto-consent existing invitees**: rejected because authenticated page processing requires an
  affirmative versioned disclosure acknowledgement.
- **Wait for statistical qualification**: rejected by the deployment owner in favor of reliability
  and immediate explicit rollout.
- **Run legacy after Browser Use failure**: rejected because same-job fallback masks reliability and
  can duplicate cost and actions.

## Consequences

### Positive

- Currently disclosed invitees receive the same Browser Use price path as the owner immediately
  after the operator selects the new mode.
- Route names and historical qualification evidence retain their meaning.
- Consent and regression remain explicit code-owned gates.
- Manual and scheduled behavior cannot drift into separate implementations.

### Negative

- Invitees may consume the owner's Anthropic budget before the statistical cost target is proven.
- Reliability issues may affect invitees while evidence is still accumulating.
- Invitees with missing or stale consent must run `/connect` and acknowledge the current disclosure
  before receiving Browser Use.
- Production configuration must explicitly select `consented_users`; merging code alone does not
  alter a bind-mounted deployment config.

## Relationship to Existing Decisions

- **ADR-036 preserved**: Browser Use remains an untrusted adapter behind BookSaver authority.
- **ADR-038 amended**: its qualified-promotion route remains, but explicit owner-authorized early
  rollout is now permitted for disclosed invitees.
- **ADR-043 preserved**: Browser Use remains the default adapter for every admitted price job.
- **ADR-044 preserved**: Browser Use remains the implementation for every agentic inventory trigger.

## Validation

- Route tests for owner, current-consent invitee, missing/stale-consent invitee, regression, and all
  historical modes.
- Coordinator tests proving disclosed invitee Browser Use admission is shared by `/checknow` and
  scheduled work.
- Config parsing and documentation tests for `consented_users`.
- Existing action, destination, session, validation, cost, and no-transaction suites.
