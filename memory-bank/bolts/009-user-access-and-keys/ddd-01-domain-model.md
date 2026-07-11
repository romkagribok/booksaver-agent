---
unit: 002-user-access-and-keys
bolt: 009-user-access-and-keys
stage: model
status: complete
updated: 2026-07-11T17:50:00Z
---

# Domain Model — User Access & Keys

> Scope: Bolt `009-user-access-and-keys` — **US-026** (access modes + router guard),
> **US-027** (hybrid billing + personal key), **US-028** (owner admin commands),
> **US-029** (user-scoped persistence, schema v7). This pass implements US-029 only;
> US-026/027/028's domain shape is captured here so the next pass builds against an
> already-agreed model. No source code in this stage.

## Bounded Context

**User Access & Keys** turns the single-owner daemon into a small self-hosted multi-user
service. It owns:

1. **Identity** — every Telegram update (and the laptop-mode owner) resolves to a `User`.
2. **Ownership/scoping** — every `Booking` (and everything that inherits scope through it)
   belongs to exactly one `User`; no repository read may cross that boundary.
3. **Access control** (US-026, not yet implemented) — `owner`/`invite` access modes, rate
   limiting of strangers.
4. **Billing** (US-027, not yet implemented) — owner-key-by-default with per-user caps,
   optional encrypted personal key.
5. **Administration** (US-028, not yet implemented) — owner commands to list/revoke users,
   switch access mode, issue invite codes.

## Value Objects / Entities

| Type | Properties | Constraints |
|------|------------|-------------|
| **User** (entity) | `user_id` (surrogate int PK), `telegram_user_id` (int, nullable — laptop owner has none), `role` (`owner`\|`user`), `access_state` (`active`\|`revoked`), `created_at`, `encrypted_key` (opaque nullable bytes) | Exactly one `owner` row exists at all times (DB-level partial unique index on `role`); `telegram_user_id` unique when present |
| **UserRole** | enum `OWNER`, `USER` | — |
| **UserAccessState** | enum `ACTIVE`, `REVOKED` | Revoked users' access-mode checks fail (US-026, not yet wired) |
| **Booking** (existing, intent 001) | unchanged — ownership lives at the persistence boundary via `bookings.user_id`, not as a domain field (see ddd-02 rationale) | — |
| **InviteCode** (US-028, future) | code, issued_by (owner), issued_at, used_by, used_at | Single-use; not modeled or persisted this pass |
| **AccessMode** (US-026, future) | enum `OWNER`, `INVITE` | Config-driven; not modeled this pass |
| **PerUserCaps** (US-027, future) | max checks/day, max LLM calls/day, messages/min | Not modeled this pass |

## Domain Rules

### Ownership & scoping (US-029 — this pass)

1. Every booking belongs to exactly one user (`bookings.user_id`, `NOT NULL`, `REFERENCES
   users(user_id)`); checks, savings, rebook sessions/events, and traces inherit scope
   transitively through their `booking_id` — no new FK column needed on those tables.
2. A pre-v7 database's existing rows all belong to the owner after migration; a fresh
   database's owner is created immediately, before any booking can be registered.
3. "List all" style reads that are exposed as owner-facing listings (bookings, savings) must
   offer a user-scoped variant; the CLI (and, later, the bot) always resolves the acting user
   first and calls the scoped variant.
4. Registration defaults to the owner when no user is specified (`user_id: int | None = None`
   at the application/repository boundary) — this is what keeps every pre-existing
   single-owner call site working unchanged.

### Access control (US-026 — future pass)

1. Every incoming Telegram update resolves to a `User` via `telegram_user_id` before any
   command dispatches.
2. `owner` mode: only the config-listed owner chat ID may act. `invite` mode: the allowlist
   grows via owner-issued single-use codes; everyone else is refused identically to `owner`
   mode. There is no public/open mode (Checkpoint 1).
3. A refused/unknown sender triggers no stateful action and no LLM call, and is rate-limited.

### Hybrid billing (US-027 — future pass)

1. A user with no personal key has all LLM work billed to the owner's key, bounded by
   per-user daily caps.
2. A user-supplied key is validated with a live call before being accepted, encrypted at rest
   (Fernet, `BOOKSAVER_SECRET_KEY`), and used for all of that user's LLM work thereafter.
3. Keys are never logged, traced, snapshotted, or echoed; the intake message is deleted where
   the Bot API allows it.
4. `/deletekey` reverts the user to owner-billed checks under caps.

### Administration (US-028 — future pass)

1. Only the owner may list/revoke users, switch access mode, or issue invite codes.
2. Revoking a user immediately blocks further access-mode checks for them (their existing
   bookings/data are untouched — no cascading delete).

## Aggregate Boundaries

- `User` is its own aggregate root (identity, access, key material).
- `Booking` remains its own aggregate root (intent 001); it does **not** hold a `User`
  reference as a domain field — ownership is a persistence-layer association
  (`bookings.user_id`), not a domain invariant the `Booking` object itself enforces. This
  keeps `Booking.create()` and every existing call site (23+ across the domain/application
  test suite) untouched; only the repository boundary (`add(booking, user_id=...)`) and the
  read-side scoping methods know about ownership. See ddd-02 for the full rationale.
