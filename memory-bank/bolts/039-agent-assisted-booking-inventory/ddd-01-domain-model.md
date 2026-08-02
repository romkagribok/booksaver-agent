---
stage: domain-model
bolt: 039-agent-assisted-booking-inventory
created: 2026-08-02T18:41:40Z
status: complete
---

# Domain Model: Agent-Assisted Booking Inventory

## Ubiquitous Language

- **Inventory operation**: One named, read-only account-page task such as entry, readiness,
  required-scope traversal, pagination/detail navigation, or interpretation.
- **Assisted observation**: A positively visible reservation candidate obtained from the bounded
  interpreter and marked with LLM provenance.
- **Conclusive traversal**: Deterministic proof that every required scope and terminal page was
  visited. Only this state may produce `InventoryCompleteness.COMPLETE`.
- **Preserved inventory**: The last caller-scoped synchronized state retained when current discovery
  is incomplete or failed.
- **Recovery outcome**: A redacted category describing not-needed, recovered, partial, unavailable,
  give-up, blocked, provider-error, or budget-exhausted assistance.
- **Assistance audit**: Caller-scoped, content-free operational metadata attached to one inventory
  synchronization run: outcome, step, provider profile, calls, token usage, actual actions, timing,
  and bounded structured progress events.

## Aggregate and Invariants

### Inventory Discovery Episode

Members:

- caller identity and authenticated session revision;
- pending/visited allowlisted operations and required scopes;
- deterministic and assisted positive observations keyed by remote reservation identity;
- shared recovery budget/call usage;
- completeness, failure, and recovery outcome.

Invariants:

1. All navigation remains on allowlisted HTTPS Booking.com reservation/detail destinations.
2. Authentication, captcha, identity conflict, unsafe action, and uninspectable destination fail
   closed and are not interpreted as layout drift.
3. Assisted evidence requires a visible stable remote identity and valid typed values.
4. Assisted evidence may fill missing positive facts but cannot replace deterministic lifecycle,
   refundable state, identity, or other authoritative facts with a negative claim.
5. Assisted evidence alone never establishes completeness, emptiness, absence, cancellation,
   completion, replacement, or removal.
6. Only conclusive traversal may mark unseen reservations absent.
7. Every actual provider call is charged to the active caller before it is made.
8. Zero remaining allowance preserves deterministic behavior and never borrows another user's key
   or budget.
9. Assistance audits contain no page text, URLs, guest or confirmation identity, screenshots,
   provider output, secrets, cookies, or hidden reasoning and are purged with the caller.

## Domain Services

- **Inventory recovery controller**: Reuses ADR-030 to recover one named browser operation and
  returns only after an authoritative verifier succeeds.
- **Positive interpretation validator**: Rejects malformed, conflicting, negative, unsafe-source,
  or identity-free candidates.
- **Positive merge policy**: Supplements missing facts while preserving deterministic facts and
  monitoring eligibility on conflict.
- **Synchronization reconciler**: Retains ADR-028 partial/complete mutation semantics.

## Domain Outcomes

- `NOT_NEEDED`: Deterministic discovery succeeded without a model call.
- `RECOVERED`: Assistance produced verified browser progress or validated observations.
- `PARTIAL`: Assistance retained positive evidence, but traversal remained inconclusive.
- `UNAVAILABLE`: No configured capability or allowance was available.
- `GAVE_UP`: The model/controller could not verify progress or evidence.
- `BLOCKED`: Authentication, verification, allowlist, or read-only safety boundary stopped work.
- `PROVIDER_ERROR`: The configured provider failed or returned an unusable response.
- `BUDGET_EXHAUSTED`: Step/check/daily allowance prevented further calls.

## Story Coverage

- **US-126**: Named account navigation and interpretation recovery.
- **US-127**: Completeness authority, positive-only merge, caller/session/action safety.
- **US-128**: Recovery outcome, call accounting, preserved-state Telegram rendering, and audit
  diagnostics.
