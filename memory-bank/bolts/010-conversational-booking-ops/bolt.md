---
id: 010-conversational-booking-ops
unit: 003-conversational-booking-ops
intent: 003-telegram-interface
type: ddd-construction-bolt
status: complete
stories:
  - 001-register-booking-via-chat
  - 002-route-alerts-to-owner
  - 003-per-user-limits
created: 2026-07-11T18:30:00Z
started: 2026-07-11T18:30:00Z
completed: 2026-07-11T19:46:16Z
current_stage: null
stages_completed:
  - name: model
    completed: 2026-07-11T18:40:00Z
    artifact: ddd-01-domain-model.md
  - name: design
    completed: 2026-07-11T18:50:00Z
    artifact: ddd-02-technical-design.md
  - name: implement
    completed: 2026-07-11T19:35:00Z
    artifact: >-
      infrastructure/telegram/{dialogs,register_dialog,commands_readonly,gateway}.py +
      infrastructure/notifications/routing.py + monitor/user_limits.py +
      monitor/search_check_job.py (run_all_active override) +
      application/{savings_pipeline,load_config,ports}.py +
      domain/{value_objects,models,check_result}.py + infrastructure/persistence/sqlite_store.py
      (get_owner_user_id) + cli/commands.py wiring
  - name: test
    completed: 2026-07-11T19:46:16Z
    artifact: ddd-03-test-report.md
requires_bolts:
  - 008-telegram-bot-gateway
requires_units:
  - 001-telegram-bot-gateway
  - 002-user-access-and-keys
blocks: false
complexity:
  avg_complexity: 4
  avg_uncertainty: 3
  max_dependencies: 4
  testing_scope: 4
---

# Bolt: 010-conversational-booking-ops

## Overview

Third bolt of intent 003. Makes Telegram a full write path for monitoring: a `/register`
guided dialog that collects a booking one field at a time — validated with the exact same
domain value objects the CLI's `register` command uses — and ends in the same `Booking`
aggregate, owned by the registering user. Savings alerts are re-routed per booking to the
owning user's own Telegram chat instead of a single fixed `telegram_chat_id`. A new
`[limits]` config section adds a per-user active-booking cap, a per-user daily check
ceiling with fair round-robin scheduling across users, an outbound per-chat message rate
limit, and an in-memory per-user daily LLM-call counter.

Ran in parallel with bolt 009 (access modes, invite codes, `/setkey`); this bolt does not
touch `access.py`, `pyproject.toml`, LLM key resolution, or the schema version.

## Objective

A bot user (owner or, once bolt 009 admits them, an invited user) can register a booking
entirely from chat with CLI-identical validation and rejection messages, sees only their
own bookings/savings/checks, gets savings alerts on their own chat, and is defended by
generous, config-overridable per-user limits that degrade politely rather than starving
other users or crashing the bot.

## Stories Included

- **US-025**: Register a booking via chat dialog (Must)
- **US-030**: Route savings alerts to the booking owner (Must)
- **US-031**: Per-user cost caps and abuse limits (Must)

## Bolt Type

**Type**: DDD Construction Bolt
**Definition**: `.specsmd/aidlc/templates/construction/bolt-types/ddd-construction-bolt.md`

## Stages

- [x] **1. Domain Model**: Complete → ddd-01-domain-model.md
- [x] **2. Technical Design**: Complete → ddd-02-technical-design.md
- [x] **3. Implement**: Complete → register dialog, alert routing, fair-scheduling/limits
- [x] **4. Test**: Complete → ddd-03-test-report.md (504/504; 45 new)

## Dependencies

### Requires
- Unit `001-telegram-bot-gateway` (bolt 008): `CommandRouter`, `DialogManager`/`DialogDefinition`
  framework, `commands_readonly.py` patterns, `gateway.py` wiring.
- Unit `002-user-access-and-keys` (bolt 009, parallel): `SqliteUserRepository`, schema v7
  `users` table + scoped booking/savings repositories. This bolt reads through those
  repositories but does not build access control itself.

### Enables
- Bolt 011 (`004-telegram-rebook-gate`) reuses the `DialogAborted` / dynamic-prompt
  extensions to `dialogs.py` for its own confirmation dialog.

## Success Criteria

- [x] `/register` collects one field per step; every answer is validated with the same
      domain value objects the CLI uses (`Property`, `StayDates`, `RoomType`, `Money`,
      `ConfirmationId`, `Occupancy`) — no rules duplicated.
- [x] A non-refundable answer aborts with the same product-constraint message the CLI's
      `BookingRejectedError` carries ("Only refundable bookings can be registered.").
- [x] The final step replays a full summary and requires explicit yes/no; no is a safe
      abort with nothing saved.
- [x] A completed dialog calls the shared `register_booking` application service, scoped to
      the sender's resolved local `user_id` — the same `Booking` aggregate the CLI produces.
- [x] `/bookings`, `/savings`, `/checks` are sender-scoped via `UserRepository
      .get_by_telegram_id`; an unresolved/revoked sender gets a polite refusal, never
      another user's data.
- [x] Per-user active-booking cap (`limits.max_bookings_per_user`, default 3) enforced at
      dialog start and re-checked at save time; the owner is exempt.
- [x] A savings alert reaches only the owning user's Telegram chat (`OwnerBookingNotifierResolver`);
      the owner keeps the existing email + static Telegram channel unchanged.
- [x] `[limits]` config section validated at load with generous defaults.
- [x] Scheduler checks bookings in fair round-robin order across users; a user at today's
      check ceiling is skipped entirely and notified once per day, not every tick.
- [x] Outbound bot replies are rate-limited per chat; a breach drops and logs, never crashes.

## Notes

- **Dialog framework extended, not replaced.** `DialogStep.validate` now also receives the
  answers collected so far (needed for `check_out > check_in` via the real `StayDates`
  value object), `DialogStep.prompt` may be a callable of those answers (the final
  confirmation step's dynamic summary), and a new `DialogAborted` exception ends a dialog
  outright with a message (a "no" answer, or a hard product-constraint rejection) instead
  of re-prompting the current step. All three are additive; bolt 008's framework tests
  needed only a two-argument `validate` signature update.
- **Booking cap: owner exempt, documented choice.** The unit brief left this open
  ("your call, document it") — the owner runs the daemon and is trusted with unlimited
  bookings; every other user is capped. Enforced twice (dialog start + save) to close a
  race where a second registration completes while the first is still in progress.
- **Future-date validation not added.** The unit's story AC mentions "future dates" among
  validated fields, but neither the CLI nor the shared domain `StayDates`/`Occupancy`
  value objects enforce it today — only `check_out > check_in`. Per this bolt's explicit
  instruction to reuse existing validators rather than duplicate rules, the dialog matches
  that behavior exactly rather than inventing a new domain rule unilaterally. A future bolt
  can add it to `StayDates` once, benefiting the CLI and every dialog at once.
- **Alert routing hook.** `NotificationDispatcher` (application/savings_pipeline.py) gained
  an optional `resolver: NotifierResolver` constructor arg (`Callable[[Booking], list[Notifier]]`);
  when given, it replaces the static `notifiers` list per booking. `_make_check_job` in
  `cli/commands.py` now builds `OwnerBookingNotifierResolver` (owner bookings keep the
  static email/Telegram list; other users route to a fresh `TelegramNotifier` addressed to
  their own `telegram_user_id`) and passes it as the resolver. An unreachable owning user
  logs a warning and sends nothing — never crashes the pipeline.
- **Fair scheduling.** `monitor/user_limits.py` (new module) is pure and unit-tested in
  isolation: `build_check_plan` round-robins each active user's bookings and excludes users
  already at `limits.max_checks_per_user_per_day`; `users_needing_capped_notice` decides
  which capped users are due today's one-time notice. `search_check_job.BookingComSearchMonitor
  .run_all_active` gained an optional `bookings` override (defaults to the pre-existing
  `list_active()` behavior) so `_make_check_job` can pass the fair-ordered plan without
  touching the monitor's internals. Skipped bookings get a `USER_CHECK_LIMIT_REACHED`
  check-history row every tick they're skipped (new `FailureCode`, no schema change —
  `failure_code` is unconstrained `TEXT`).
- **Counters are in-memory, process-lifetime.** `DailyCounter` (checks-per-user,
  capped-notice-sent-per-user) is created once per daemon start and reset at UTC midnight;
  a daemon restart loses today's counts. Documented as an accepted trade-off (ADR-003
  stdlib-first; these are abuse safety nets, not billing) rather than adding a schema bump
  or new table this bolt doesn't own.
- **LLM daily-call ceiling: tracked, not yet enforced.** `limits.max_llm_calls_per_user_per_day`
  is validated and shipped in config, but wiring a hard per-user LLM suppression into the
  check loop would require splitting `BookingComSearchMonitor`'s single shared LLM
  extractor/agent-brain per booking mid-tick — real surgery on bolt 007's agent loop that
  didn't fit this bolt's scope. Left as a documented follow-up; the counter's home
  (`DailyCounter`) is ready for a future bolt to wire in.
- **Coordination:** did not touch `access.py`, `pyproject.toml`, LLM key resolution, invite
  codes, or `SCHEMA_VERSION` (still 7). Shared files (`gateway.py`, `load_config.py`,
  `cli/commands.py`, `story-index.md`) were edited with additive, clearly delimited blocks
  per the coordination note; the parallel bolt-009 worker's `access.py` rewrite will need to
  reconcile `gateway.py`'s owner-guard-based admission with this bolt's `UserRepository
  .get_by_telegram_id` sender resolution in the readonly/register commands (currently a
  sender must already have a `users` row with a matching `telegram_user_id` — bolt 009's
  admission flow is expected to create/link that row before a command handler runs).
