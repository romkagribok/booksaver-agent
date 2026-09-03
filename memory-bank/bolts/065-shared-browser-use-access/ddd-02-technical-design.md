---
stage: design
bolt: 065-shared-browser-use-access
created: 2026-09-03T23:38:00Z
---

# Technical Design: Shared Browser Use Access

## Architecture Pattern

Extend the existing closed route resolver and aggregate admin projection rather than creating a new
execution path. The coordinator remains the only manual/scheduled price admission point, and the
existing Browser Use factory, session lease, action guards, cost ledger, validator, and inventory
admission remain unchanged.

Add `consented_users` as an explicit configuration value. It admits the owner and currently
disclosed active invitees, but does not alter the existing `agentic` qualification contract or
persist promotion state. A regressed qualification state remains an unconditional rollback signal.

Extend the owner-only `AdminUserAggregate` with one boolean derived in SQL from encrypted-key
nullability. Presentation combines it with the fixed code-owned statement that Browser Use is
owner-funded. No key store or decryption adapter is reachable from this query.

## Layer Structure

```text
Configuration
    │
    ▼
ExecutionRoutingMode.CONSENTED_USERS
    │
    ▼
PriceRouteResolver ─── current disclosure + regression ───► RoutingDecision
    │                                                       │
    └──────── same coordinator path for /checknow + schedule ┘
                                                            │
                                                            ▼
                                              Existing Browser Use executor

SQLite users ── aggregate SELECT (encrypted_key IS NOT NULL) ──► AdminUserAggregate
                                                                    │
                                                                    ▼
                                                        Owner-only /admin users
```

## Component Design

### Price routing

- Add `CONSENTED_USERS = "consented_users"` to the closed price routing enum.
- Preserve parsing failure for every unknown value.
- In route resolution, keep `legacy` first and regression second.
- For `consented_users`, admit owners with a dedicated owner-rollout reason. Admit invitees only
  after exact current-disclosure match with a dedicated consented-invitee reason. Otherwise return
  `disclosure_required`.
- Preserve `owner_canary` and qualification-gated `agentic` branches unchanged.
- Do not update the qualification repository during resolution.

### Manual and scheduled execution

- Continue resolving the route only inside the coordinator's shared booking execution method.
- No Telegram-command or scheduler-specific executor selection is added.
- Existing active-user authorization occurs before resolution; tests exercise both trigger paths to
  prevent divergence.

### Inventory execution

- No production code change is required. Existing `inventory_routing = "agentic"` already admits
  the owner and currently disclosed active invitees and selects the shared Browser Use inventory
  adapter for every trigger.
- Preserve `inventory_routing = "legacy"` as explicit rollback.

### Admin aggregate

- Add `personal_key_configured: bool` to `AdminUserAggregate`.
- Select `u.encrypted_key IS NOT NULL` in the existing aggregate SQL and group without loading the
  blob into Python.
- Format a separate line per user:
  `API funding: Browser Use=deployment owner; personal legacy key=configured|not configured`.
- Keep the line independent of the runtime usage provider so it remains present when counters are
  unavailable.
- Do not display costs or historical key attribution because cost attempts do not persist key
  provenance.

## Data Model

No schema migration. Existing inputs are read-only:

- `users.encrypted_key IS NOT NULL` → `personal_key_configured: bool`
- configured disclosure version + stored consent → invitee admission
- existing qualification state → regression dominance or qualified-mode admission

No new table, persisted key metadata, or admin audit record is introduced.

## Security Design

- Invitee consent remains an exact version match before authenticated page processing.
- Unknown, revoked, or inactive users remain denied before route resolution.
- Admin output remains private-owner-only and uses an allowlisted DTO.
- Key presence is derived without selecting, decrypting, logging, hashing, validating, or formatting
  ciphertext.
- Browser Use always uses `BOOKSAVER_LLM_API_KEY`; personal keys remain legacy-only.
- Existing browser destination/action/transaction guards and hard limits are untouched.

## NFR Implementation

- **Privacy**: Retain sentinel tests for raw key, Telegram ID, booking identifiers, property, price,
  failure, and trace content. Add assertions for only the two allowed coarse key states.
- **Reliability**: Preserve one shared coordinator route for manual and scheduled work and verify the
  new decision under owner, consented invitee, missing/stale consent, and regression states.
- **Compatibility**: Keep existing routing modes and default-safe legacy behavior. Operators opt into
  the new mode explicitly.
- **Observability**: Admin labels state current funding policy only; they make no historical billing
  claim.

## Verification Design

- Domain tests for all `consented_users` decisions and unchanged legacy/canary/qualified behavior.
- Config tests accepting the new value and rejecting unknown values.
- Coordinator tests proving an unqualified but disclosed invitee receives Browser Use for immediate
  and scheduled price work.
- Persistence/admin tests proving boolean projection and raw-key exclusion.
- Telegram tests proving owner visibility, non-owner refusal, exact-data isolation, and availability
  independent of runtime counters.
- Full Ruff, mypy, pytest, CLI startup, artifact validation, status integrity, and diff checks before
  review.
