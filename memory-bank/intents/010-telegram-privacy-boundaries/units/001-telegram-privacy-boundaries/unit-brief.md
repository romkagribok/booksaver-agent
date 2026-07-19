---
unit: 001-telegram-privacy-boundaries
intent: 010-telegram-privacy-boundaries
phase: inception
status: complete
unit_type: cli
default_bolt_type: simple-construction-bolt
created: 2026-07-19T02:34:19Z
updated: 2026-07-19T14:48:51Z
---

# Unit Brief: Telegram Privacy Boundaries

## Purpose

Make privacy enforceable across every Telegram surface so exact booking-derived data never crosses
user ownership, owner administration remains aggregate-only, non-private chats cannot reach handlers,
and revocation is honored by queued/completing work and outbound messaging.

## Scope

### In Scope

- Carry trusted Telegram chat type through message and callback envelopes.
- Reject non-private updates before command, callback, dialog, key, database, browser, or LLM paths.
- Replace global `/status` enumeration with caller-safe health and aggregate information.
- Centralize caller-owned exact record resolution and mask foreign confirmation conflicts.
- Supply a dedicated allowlisted admin usage projection.
- Reauthorize scheduled/immediate checks, rebook prompts/handoffs, cap/key notices, and alerts.
- Prove every command/callback/dialog/completion/notification boundary with two-user sentinels.

### Out of Scope

- Hiding local files, logs, SQLite, traces, or snapshots from the owner/root VPS operator.
- A web dashboard, downloadable analytics, public bot mode, or additional admin roles.
- Persisted analytics counters, client-side encryption, or a privacy-specific schema migration.
- Changing Booking.com equivalence, price, refundability, or guided-rebook confirmation rules.

## Assigned Requirements

| FR | Requirement | Priority |
|----|-------------|----------|
| FR-1 | Restrict interaction to private Telegram chats | Must |
| FR-2 | Scope status and exact-data selectors to the caller | Must |
| FR-3 | Restrict owner administration to aggregate usage | Must |
| FR-4 | Make revocation immediate across asynchronous work and messages | Must |
| FR-5 | Prove isolation by construction and adversarial regression | Must |

## Domain Concepts

### Key Concepts

| Concept | Description | Relevant attributes |
|---------|-------------|---------------------|
| Trusted update envelope | Bot API identity/context used for authorization | sender ID, chat ID/type, family |
| Caller scope | Active local user and owned booking-derived records | user ID, ownership relation |
| Aggregate admin usage | Explicitly allowed operational counts without exact records | label, state, counts |
| Revocation boundary | Point where async work/delivery revalidates access | user, ownership, operation |
| Privacy sentinel | Unique test marker that must never reach another user | properties, IDs, prices, failures |

### Key Operations

| Operation | Description | Inputs | Outputs |
|-----------|-------------|--------|---------|
| Admit update | Require private chat and active sender before routing | update metadata | admitted/refused envelope |
| Resolve owned data | Select exact data inside caller ownership only | user, selector | record or generic absence |
| Project admin usage | Query only approved identity/access/count fields | owner request, counters | aggregate rows |
| Reauthorize async work | Recheck access and ownership at execution/delivery seams | user, record, operation | continue/terminate |
| Assert isolation | Run two-user matrix over every adapter family | sentinel fixtures | zero-disclosure proof |

## Story Summary

| Metric | Count |
|--------|-------|
| Total Stories | 5 |
| Must Have | 5 |
| Should Have | 0 |
| Could Have | 0 |

### Stories

| Story ID | Title | Priority | Status |
|----------|-------|----------|--------|
| US-067 | Restrict interaction to private chats | Must | Complete |
| US-068 | Scope status and selectors | Must | Complete |
| US-069 | Show aggregate admin usage | Must | Complete |
| US-070 | Stop work after revocation | Must | Complete |
| US-071 | Prove cross-user isolation | Must | Complete |

## Dependencies

### Depends On

| Capability | Reason |
|------------|--------|
| Bolt 021 / sharing experience | Supplies final username identity shape and invite-only flow |
| Bolt 017 / booking management | Supplies caller-selected edit/delete command and callback families |
| Bolt 019 / on-demand checks | Supplies coordinator admission, completion, and per-user counters |
| Intent 003 / Telegram interface | Supplies router, dialogs, access, notifications, and rebook gate |

### Depended By

| Consumer | Reason |
|----------|--------|
| Owner-operated shared bot | Needs a verified isolation boundary before broader invitations |
| Future Telegram features | Must reuse scoped exact-data and aggregate-admin services |

### External Dependencies

| System | Purpose | Risk |
|--------|---------|------|
| Telegram Bot API | Authoritative sender/chat type and private delivery | Medium |
| Booking.com | Browser work after authorization | High |
| Anthropic API | Bounded work after authorization | Medium |
| SQLite | Ownership and aggregate projections | Medium |

## Technical Context

Use the existing Python 3.11 stdlib Telegram client, immutable command/callback envelopes, SQLite
ownership joins, synchronous coordinator, and confirmation state machine. Prefer small caller-scoped
application/query services over repeated raw unscoped repository access in adapters. Feed the existing
in-memory daily counter snapshots into the admin projection and label their reset semantics.

## Constraints

- Telegram metadata, not user text, determines sender and chat type.
- Owner privilege never bypasses record ownership.
- Foreign and absent selectors remain indistinguishable.
- Denials precede state, key validation, browser, LLM, and outbound exact-data work.
- The v9 username from Intent 009 is display-only; authorization uses immutable IDs.
- No privacy-specific database migration or dependency.

## Success Criteria

### Functional

- [x] Group/supergroup/channel updates cannot enter any handler or disclose exact data.
- [x] `/status` and every exact selector/callback are caller-scoped and non-enumerating.
- [x] Admin Telegram output contains only approved identity/access/usage counts.
- [x] Revoked users receive no later sensitive completion, prompt, handoff, notice, or alert.
- [x] Existing active owners retain all caller-owned functionality.

### Non-Functional

- [x] Two-user sentinels prove zero cross-user disclosure or mutation.
- [x] Privacy denial adds no external dependency, process, or persistence schema.
- [x] Full Ruff, mypy, pytest, and diff gates pass; AI-DLC validation has no new issues beyond 38 historical findings.

### Quality

- [x] All five stories have focused automated coverage.
- [x] Concurrency tests deterministically cover revocation timing seams.
- [x] Human final review occurred before closure, commit, and push.

## Bolt Suggestion

| Bolt | Type | Stories | Objective |
|------|------|---------|-----------|
| `022-telegram-privacy-boundaries` | Simple Construction | US-067–US-071 | Deliver and prove the cohesive Telegram privacy policy |

## Notes

Construction is intentionally blocked on Bolt 021 so privacy code targets the final invite-only access
and username identity model rather than racing its schema and command-surface changes.
