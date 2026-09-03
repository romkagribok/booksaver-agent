---
unit: 007-shared-browser-use-access
intent: 023-replaceable-agentic-browser-executor
phase: construction
status: complete
created: 2026-09-03T23:30:00.000Z
updated: 2026-09-03T23:40:07Z
unit_type: backend
default_bolt_type: ddd-construction-bolt
---

# Unit Brief: Shared Browser Use Access

## Purpose

Extend the proven Browser Use path from the deployment owner to every active invited user who has
accepted the current disclosure, and make the owner-only Telegram administration view explain the
effective API funding policy without exposing API-key material.

## Scope

### In Scope

- An explicit `consented_users` price-routing mode distinct from owner canary and statistically
  qualified promotion.
- Identical Browser Use price routing for disclosed invitees across `/checknow` and scheduled work.
- Preservation of the existing consent gate for authenticated page processing.
- Owner-only display of Browser Use funding and coarse personal legacy-key presence.
- Aggregate-only SQL projection; no key decryption, fingerprinting, or schema migration.
- Documentation of the narrow supersession of older invitee-qualification and admin-key-visibility
  restrictions.

### Out of Scope

- Removing disclosure consent, auto-consenting existing users, or processing undisclosed page data.
- Changing Browser Use to consume personal user API keys.
- Historical per-key cost attribution, provider billing reconciliation, or a new spend dashboard.
- Automatic same-job fallback, legacy selector retirement, or additional browser providers.
- Production deployment; this bolt ends at merge and leaves deployment to a later operation.

## Assigned Requirements

| FR | Requirement | Priority |
|----|-------------|----------|
| FR-21 | Consented invited-user Browser Use parity | Must |
| FR-22 | Secret-safe admin API funding visibility | Must |

## Domain Concepts

- **ConsentedUsersRoute**: Explicit operator-selected route admitting the owner and currently
  disclosed active invitees without mutating qualification evidence.
- **DisclosureAdmission**: Current version match required before an invitee's authenticated page
  content may reach Anthropic.
- **FundingProvenance**: Human-readable policy that agentic Browser Use uses the deployment owner's
  environment key.
- **PersonalLegacyKeyPresence**: Boolean aggregate fact that an encrypted personal key exists; it is
  not a key representation and is never decrypted for administration.

## Story Summary

| Metric | Count |
|--------|-------|
| Total Stories | 2 |
| Must Have | 2 |
| Should Have | 0 |
| Could Have | 0 |

| Story ID | Title | Priority | Status |
|----------|-------|----------|--------|
| US-170 | Route disclosed invitees through Browser Use | Must | Complete |
| US-171 | Show secret-safe API-key provenance | Must | Complete |

## Dependencies

- Unit 001 routing and control-plane contracts.
- Unit 003 qualification and regression state.
- Unit 004 Browser Use inventory execution and disclosure persistence.
- Unit 006 Browser Use price executor and shared manual/scheduled path.
- Intent 010 owner-only aggregate Telegram administration boundary.

## Constraints

- A recorded regression remains stronger than early rollout configuration.
- Active-user authorization and current disclosure are checked before Browser Use admission.
- Browser Use remains owner-funded even when a personal legacy key exists.
- No API key, encrypted value, fingerprint, suffix, prefix, or provider validation detail enters an
  admin DTO, log, trace, or Telegram response.

## Success Criteria

- [x] Owner and currently disclosed active invitees are admitted by `consented_users` while
  undisclosed, revoked, regressed, and explicitly legacy cases fail closed.
- [x] `/checknow` and scheduled work share the same invitee price route.
- [x] `/admin users` states the Browser Use funding policy and coarse personal legacy-key presence.
- [x] Existing aggregate privacy sentinels prove no key or exact booking data is exposed.
- [x] Focused and full repository quality gates pass.

## Bolt Suggestions

- `065-shared-browser-use-access`: US-170 and US-171.
