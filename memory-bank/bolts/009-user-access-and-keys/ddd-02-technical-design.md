---
unit: 002-user-access-and-keys
bolt: 009-user-access-and-keys
stage: design
status: complete
updated: 2026-07-11T19:42:53Z
---

# Technical Design — User Access & Keys

> Scope: US-026, US-027, US-028, US-029. This pass implements US-029 only (marked below);
> the rest is the agreed design for the next pass of this bolt.

## Module Map

| Module | Role | New/Changed | Story |
|--------|------|--------------|-------|
| `domain/user.py` | `User`, `UserRole`, `UserAccessState` | **new** | US-029 |
| `infrastructure/persistence/schema.sql` + `sqlite_store.py` | v7: `users` table (+ partial unique index enforcing one owner), `bookings.user_id`; `_migrate_v7`; `_ensure_owner_user`; `SqliteUserRepository` | **new/changed** | US-029 |
| `application/ports.py` | + `UserRepository` Protocol; `BookingRepository.add(booking, user_id=None)` + `list_active_for_user`/`list_all_for_user`; `SavingsRepository.list_all_for_user`; + `LLMClientFactory` Protocol | changed | US-029 |
| `application/register_booking.py` | + optional `user_id` param threaded to `repo.add()` | changed | US-029 |
| `infrastructure/llm/client_factory.py` | `AnthropicLLMClientFactory` — `for_booking`/`agent_brain_for_booking`, today always owner-key | **new** | US-029 |
| `cli/commands.py` | `cmd_register`/`cmd_bookings_list`/`cmd_savings_list` resolve the owner user first; `_make_llm_extractor`/`_make_agent_brain` refactored to go through the factory | changed | US-029 |
| `infrastructure/telegram/*` | update loop, router, dialog machine — owned by bolt 008 | n/a here | — |
| `infrastructure/telegram/access_guard.py` (future) | Resolves `User` from update, enforces access mode, rate-limits strangers | **new (future)** | US-026 |
| `infrastructure/config/toml_env_source.py` (future) | `[access]` section: `mode = "owner" \| "invite"`, owner chat id list | changed (future) | US-026 |
| `infrastructure/crypto/fernet_key_store.py` (future) | Encrypt/decrypt `users.encrypted_key` with `BOOKSAVER_SECRET_KEY` | **new (future)** | US-027 |
| `infrastructure/llm/client_factory.py` (future) | `for_booking` resolves booking → owning user → decrypted personal key, else owner key + caps | changed (future) | US-027 |
| `cli/commands.py` / bot admin commands (future) | list/revoke users, switch mode, issue invites | changed (future) | US-028 |

## Schema v7 (US-029 — implemented)

```sql
CREATE TABLE IF NOT EXISTS users (
    user_id          INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_user_id INTEGER UNIQUE,
    role             TEXT    NOT NULL CHECK(role IN ('owner', 'user')),
    access_state     TEXT    NOT NULL DEFAULT 'active'
        CHECK(access_state IN ('active', 'revoked')),
    encrypted_key    BLOB,
    created_at       TEXT    NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_users_single_owner
    ON users(role) WHERE role = 'owner';

-- bookings gains, at the end of its existing column list:
    user_id INTEGER NOT NULL REFERENCES users(user_id)

CREATE INDEX IF NOT EXISTS idx_bookings_user ON bookings(user_id);
```

`check_history`, `savings_opportunities`, `rebook_sessions`, `rebook_events`, `check_traces`
are unchanged — they inherit scope through `booking_id`, joined against `bookings.user_id`
where a user-scoped read is needed (e.g. `SqliteSavingsRepository.list_all_for_user`).

### Migration mechanics (`_migrate_v7`)

Follows `_migrate_v5`'s pattern for a structural change SQLite can't do in place (adding a
`NOT NULL REFERENCES` column to a table with existing rows):

1. Create `users` (+ partial unique index) if it doesn't exist yet (migrations run *before*
   `schema.sql`'s idempotent `CREATE TABLE IF NOT EXISTS`).
2. `_ensure_owner_user` — idempotent: returns the existing owner's id, or inserts one
   (`telegram_user_id = NULL`, `role = 'owner'`, `access_state = 'active'`).
3. If `bookings.user_id` doesn't exist: create `bookings_v7` with the full v7 column set,
   `INSERT ... SELECT <old columns>, <owner_id> FROM bookings`, then swap tables.
4. Step 3 needs `PRAGMA foreign_keys=OFF` bracketing the swap — `check_history` /
   `rebook_sessions` hold (unenforced-but-checked-on-DDL) `REFERENCES bookings(booking_id)`,
   and SQLite refuses to `DROP TABLE` a table something else references while
   `foreign_keys=ON`, even with zero orphaned rows. The pragma only takes effect with no
   pending transaction, hence the `commit()` immediately before toggling it.
5. **Fresh init** skips the migration loop entirely (`schema.sql` already creates the v7
   shape empty) — so `SqliteStore._apply_schema` calls `_ensure_owner_user` unconditionally
   *after* `executescript`, which is a no-op on an already-migrated DB and creates the owner
   on a brand-new one.

### Why ownership is NOT a `Booking` domain field

`Booking.create()` and `BookingRegistrationService.register()` have no `user_id` parameter,
and the `Booking` dataclass carries none. Ownership is recorded only at the persistence
boundary: `BookingRepository.add(booking, user_id: int | None = None)`. Rationale:

- Every pre-existing call site (23+ `register_booking(...)` calls across the domain/
  application test suite, plus `BookingRegistrationService.register()`'s own ~8 direct
  callers) stays untouched — `user_id` defaults to `None`, and the SQLite adapter resolves
  the owner automatically when it's omitted, so single-owner behavior is provably unchanged
  by construction, not just by test coverage.
- Scoped reads (`list_active_for_user`, `list_all_for_user`) return plain, owner-blind
  `Booking` objects — the caller already knows whose data it asked for; the object doesn't
  need to carry it redundantly.
- If a future slice needs a booking to know its own owner in-memory (e.g. the per-user LLM
  key resolution in US-027), that's an additive `Booking.user_id: int | None = None` field
  at that point — no migration of this design is required to add it later.

## `LLMClientFactory` seam (US-029 — implemented)

```python
class LLMClientFactory(Protocol):
    def for_booking(self, booking: Booking | None) -> LLMExtractor | None: ...
    def agent_brain_for_booking(self, booking: Booking | None) -> AgentBrain | None: ...
```

`AnthropicLLMClientFactory` (the only implementation) resolves `BOOKSAVER_LLM_API_KEY`
regardless of `booking` — byte-for-byte the same behavior `_make_llm_extractor`/
`_make_agent_brain` had before this bolt (including the DOM-only/scripted-only degradation
on a missing key or missing `anthropic` package). `cli/commands.py`'s two factory functions
are now two-line wrappers that build the factory and call it with `booking=None` — the
check-batch loop in `monitor/search_check_job.py` still constructs one `LLMExtractor`/
`AgentBrain` per scheduler tick, not per booking, so `None` is honest about what's available
at that call site today.

**Future (US-027)**: `for_booking`/`agent_brain_for_booking` resolve booking → owning user
(a `BookingRepository`/`UserRepository` lookup the factory would need injected) →
decrypted personal key if set, else owner key + per-user cap check. No call site changes;
only `AnthropicLLMClientFactory`'s internals and constructor dependencies change.

## Repository Scoping Boundary (US-029 — implemented)

| Repository | Unscoped (unchanged) | Scoped (new) |
|-------------|----------------------|---------------|
| `BookingRepository` | `get_by_id`, `get_by_confirmation`, `exists`, `set_occupancy`, `list_active` (all-users, used by the scheduler), `list_all` | `add(booking, user_id=None)`, `list_active_for_user(user_id)`, `list_all_for_user(user_id)` |
| `SavingsRepository` | `get`, `list_for_booking`, `list_all`, `mark_notified` | `list_all_for_user(user_id)` (JOIN `bookings` on `user_id`) |
| `UserRepository` | — (new repository, all methods are user-management primitives) | `get_owner`, `get_by_id`, `get_by_telegram_id`, `get_or_create_by_telegram_id`, `list_all`, `list_active`, `set_access_state` |

`get_by_id`/`get_by_confirmation`/`set_occupancy` stay unscoped because every current call
site reaches them with an already-known, unguessable UUID or a Booking.com confirmation
number obtained from a trusted context (CLI arg the user typed, or an id resolved from a
prior scoped list). **Known follow-up**: once the bot gateway (bolt 008) routes untrusted
Telegram input directly into booking-id lookups (e.g. a `/checks <booking_id>` command),
those lookups should gain an explicit `user_id` ownership check rather than relying on the
id being unguessable. Track this as part of US-030 (bolt 010) wiring, not a gap in this
bolt's stated scope.

## CLI wiring (US-029 — implemented)

`cmd_register`, `cmd_bookings_list`, `cmd_savings_list` each call
`SqliteUserRepository(store).get_owner()` once and pass `owner.user_id` into the scoped
repository methods. Output is byte-identical to pre-v7 behavior for a laptop (single-owner)
database, since the owner is the only user.

## Test Strategy (US-029)

- **Migration**: `tests/integration/test_user_scoping.py::TestV7Migration` — a hand-built v6
  DDL (two legacy bookings) migrates to v7 with exactly one owner row and both bookings
  reassigned; migration is idempotent on reopen; fresh init creates v7 directly; a
  registration + listing round trip on a fresh "laptop" DB is unchanged.
- **Invariant**: `TestExactlyOneOwner` — inserting a second `role='owner'` row raises
  `sqlite3.IntegrityError` (partial unique index).
- **`UserRepository`**: `TestUserRepository` — `get_or_create_by_telegram_id` idempotency,
  `set_access_state` revocation + unknown-user `KeyError`.
- **Cross-user isolation** (`TestCrossUserIsolation`): two users, one booking each; asserts
  `list_active_for_user`/`list_all_for_user`/`SavingsRepository.list_all_for_user` for user A
  never contains user B's rows (and vice versa).
- **Factory**: `tests/unit/test_llm_client_factory.py` — missing key → `None` for both
  extractor and brain; present key → both constructed; passing a `Booking` vs `None` doesn't
  change resolution this slice.
- Full existing suite (360 tests) re-verified green; two `SavingsRepository` fakes
  (`tests/unit/savings/test_pipeline.py`, `tests/unit/rebook/test_rebook_service.py`) and the
  shared `FakeBookingRepository` (`tests/unit/monitor/fakes.py`) gained the new protocol
  methods so mypy structural conformance holds.

## Implementation notes (US-026/027/028 pass, 2026-07-11T19:42:53Z)

The module map above was followed with these refinements, made while implementing:

| Module | What actually landed |
|--------|----------------------|
| `infrastructure/telegram/access.py` | `AccessControl` added **alongside** (not replacing) `OwnerGuard` — bolt 008's tests construct `OwnerGuard` directly, and keeping it avoids an unrelated test rewrite. Production wiring (`gateway.py`) uses `AccessControl` exclusively. |
| `infrastructure/persistence/schema.sql` / `sqlite_store.py` | Schema **v8**: `invite_codes` (code PK, issued_by/used_by FK → users, issued_at, expires_at, used_at), purely additive — no `_migrate_v8` function needed (same pattern as v3/v4/v6). `SqliteUserRepository` gained `get_owner_of_booking`, `set_encrypted_key`, `purge`; new `SqliteInviteCodeRepository` (`issue`/`redeem`/`get`). |
| `application/ports.py` | `UserRepository` extended with the three new methods; new `InviteCodeRepository` Protocol. |
| `infrastructure/crypto/fernet_key_store.py` | **New** (not anticipated as a separate package in ddd-01, which named it `fernet_key_store.py` directly under `infrastructure/`) — `FernetKeyStore.encrypt`/`decrypt`, lazy `BOOKSAVER_SECRET_KEY` read (constructing the store never fails; only an actual encrypt/decrypt call can raise `SecretKeyError`), so an owner-only deployment that never sets the env var is unaffected. |
| `infrastructure/telegram/key_validator.py` | **New** — `KeyValidator` Protocol + `AnthropicKeyValidator` (one `client.models.list(limit=1)` call). Faked in tests. |
| `infrastructure/telegram/key_dialogs.py` | **New** — `KeyIntakeFlow` (`/setkey`) and `handle_deletekey` (`/deletekey`). `KeyIntakeFlow` is deliberately **not** built on `DialogManager`/`DialogDefinition`: that framework's `on_complete(user_id, chat_id, answers)` doesn't receive the raw Telegram `message_id`, which is required to delete the chat message containing the pasted key. A small per-chat pending-set is simpler than extending the shared dialog machinery's signature for one caller (which bolt 010's `/register` dialog also uses and shouldn't need to change). |
| `infrastructure/telegram/admin_commands.py` | **New** — `register_admin_commands` wires `/admin users\|revoke\|purge\|invite\|mode`. Every branch re-checks `access_control.is_owner` independently (never trusts "reached the handler" alone). `purge`/`mode` require an explicit `... confirm` resend rather than an inline-keyboard confirmation (inline keyboards are bolt 011's rebook-gate concern; a resend-to-confirm pattern needed no new Bot API surface). |
| `infrastructure/llm/client_factory.py` | `AnthropicLLMClientFactory` gained `user_repo`/`key_store` constructor params. `_resolve_api_key(booking)`: booking → `user_repo.get_owner_of_booking(booking.booking_id)` → if `encrypted_key` set, `key_store.decrypt(...)`, raising `UserKeyInvalidError(user_id)` on failure; else the owner env-var key (unchanged). `for_booking`/`agent_brain_for_booking` propagate the exception rather than swallowing it. |
| `monitor/search_check_job.py` | `BookingComSearchMonitor` gained an **additive** `llm_factory: LLMClientFactory \| None` constructor param. When set, `_run_check_inner` re-resolves `self._llm`/`self._brain` per booking at the top of the method (mutating the instance attributes the rest of the method already reads — matching the existing `self._last_escalator` per-call-reset pattern) instead of using the constructor-injected `llm`/`brain`. A `UserKeyInvalidError` short-circuits to `CheckResult.failure(..., FailureCode.USER_KEY_INVALID)` before the occupancy check. Every existing test/call site that passes `llm=`/`brain=` directly (no `llm_factory`) is byte-identical to before — `llm_factory` defaults to `None`. |
| `cli/commands.py` | `_make_check_job`'s `_job()` now builds one `AnthropicLLMClientFactory` per tick (with `user_repo`/`key_store` wired from the tick's open `SqliteStore`) and passes it as `llm_factory=` instead of pre-resolving `llm`/`brain` once for all bookings — this is what makes per-booking key resolution possible without changing `BookingComSearchMonitor`'s per-tick construction pattern. A new `_notify_invalid_user_keys` helper sends a direct Telegram DM (best-effort, self-contained — not routed through the general notifier, which only handles savings) to a user whose personal key failed. |
| `domain/check_result.py` | `FailureCode.USER_KEY_INVALID = "user_key_invalid"` added next to the bolt-007 agentic-escalation codes. |
| `domain/errors.py` | `UserKeyInvalidError(user_id, detail)` and `SecretKeyError` added — both `BookSaverError` subclasses. |
| `monitor/trace.py` | `redact()` extended with a second, unconditional `sk-ant-[A-Za-z0-9_-]{10,}` pattern (Anthropic keys are shaped distinctively regardless of a `key=`/`token=` label) — applied in addition to, not instead of, the existing labelled-secret pattern. |
| `infrastructure/telegram/router.py` | `IncomingCommand` gained `message_id: int = 0` (default preserves every existing construction site). |
| `infrastructure/telegram/bot_loop.py` | `access_guard`/`on_refused` callback types changed from `Callable[[int], bool/None]` to `Callable[[IncomingCommand], bool/None]` — `invite` mode's `/start <code>` admission needs the command and args, not just the chat id. Command parsing was moved before the access-guard call (was after) so the guard can see it. |
| `infrastructure/telegram/gateway.py` | `OwnerGuard` swapped for `AccessControl`; `/setkey`/`/deletekey`/`/admin *` registered in a clearly delimited block per the coordination note (bolt 010 registers its own commands in the same file). `/cancelflow` now also cancels a pending `KeyIntakeFlow`. |
| `pyproject.toml` | `cryptography>=42` added to `dependencies` (ADR-019). |

No deviation from the ddd-01 domain rules; see ddd-03-test-report.md for full verification.
