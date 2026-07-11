# Unit Brief: User Access & Keys

**Unit ID:** `002-user-access-and-keys`
**Intent:** `003-telegram-interface`
**Status:** Planned
**Build order:** 2

## Purpose

Turn the single-user daemon into a small self-hosted multi-user service. Adds a `users` table and
user-scoped repositories (schema v7; existing rows migrate to the owner), configurable access modes
(`owner` / `invite` — no public mode, per Checkpoint 1), hybrid LLM billing (owner key + per-user
caps by default; optional personal Anthropic key intake with validation and encryption at rest), a
per-user LLM client factory used by checks, and owner admin commands. This is the unit that makes a
**discoverable** bot safe: strangers get past nothing, and invited users can never see others' data
or exceed their capped share of the owner's LLM budget.

## Dependencies on other units

| Unit | What this unit needs |
|------|----------------------|
| `001-telegram-bot-gateway` | Router + dialog machine for `/setkey`, `/deletekey`, invite-code entry, admin commands |
| intent-001 `001-core-local-data` | SQLite migration framework (v6 → v7), config validation |
| intent-002 units | `LLMClient`/agent construction seam — swap fixed env-var key for per-user resolution |

## Downstream consumers

- Unit 3 scopes registration/alerts per user and enforces per-user limits.
- All check jobs resolve their LLM client through the per-user factory.

## Loose coupling / interfaces (design-level)

| Consumes | From |
|----------|------|
| `IncomingCommand` + dialogs | gateway |
| `BOOKSAVER_SECRET_KEY` env var (encryption key), owner LLM key env var | config |

| Emits | To |
|-------|-----|
| `User(user_id, access_state, has_key)` | repositories, router guard |
| `LLMClientFactory.for_booking(booking) -> LLMClient` | check jobs (owner key or user key) |
| `USER_KEY_INVALID` / `ACCESS_DENIED` failure codes | check history, bot replies |

## Recommended implementation order (within unit)

1. US-029 — users table, v7 migration, repository scoping
2. US-026 — access modes + router guard + rate limiting of strangers
3. US-027 — hybrid billing: owner-key default + optional key intake dialog, validation call, encrypted store, redaction, rotation/deletion
4. US-028 — owner admin commands (list/revoke users, switch mode, issue invite codes)

## Completion criteria (unit-level)

- v7 migration assigns existing data to owner; laptop mode behaves identically.
- A stranger (not allowlisted, no valid invite code) gets one polite refusal, is rate-limited, and
  can trigger no stateful action or LLM call in either mode.
- An invited user's checks run on the owner key under per-user caps until they `/setkey`; after
  `/setkey`, their checks bill their own key; `/deletekey` reverts to owner-billed.
- Keys never appear in logs, traces, snapshots, or replies; user can rotate and delete.
- Repository layer makes cross-user reads impossible; integration tests prove isolation.

---

## Story Files

- `US-026`
- `US-027`
- `US-028`
- `US-029`
