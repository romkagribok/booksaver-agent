---
unit: 003-conversational-booking-ops
bolt: 010-conversational-booking-ops
stage: design
status: complete
updated: 2026-07-11T18:50:00Z
---

# Technical Design — Conversational Booking Ops

> Scope: US-025, US-030, US-031. No new runtime deps (ADR-003 stdlib-first held). No
> `SCHEMA_VERSION` bump (still 7) — `get_owner_user_id` and `USER_CHECK_LIMIT_REACHED` are
> additive reads/enum values over the existing v7 schema.

## Module Map

| Module | Role | New/Changed |
|--------|------|--------------|
| `domain/value_objects.py` | + `LimitsSettings` (`max_bookings_per_user`, `max_checks_per_user_per_day`, `max_llm_calls_per_user_per_day`, `messages_per_minute_per_chat`, all `>= 1`) | changed |
| `domain/models.py` | `Config` + `limits_settings: LimitsSettings` (default-factory, additive) | changed |
| `domain/check_result.py` | `FailureCode` + `USER_CHECK_LIMIT_REACHED` | changed |
| `application/load_config.py` | `[limits]` section parsing block (delimited, additive — does not touch `[telegram_bot]` parsing) | changed |
| `application/ports.py` | `BookingRepository` + `get_owner_user_id(booking_id) -> int \| None` | changed |
| `application/savings_pipeline.py` | `NotificationDispatcher.__init__` gains optional `resolver: NotifierResolver`; `notifiers` becomes optional; `resolver` wins when both given | changed |
| `infrastructure/persistence/sqlite_store.py` | `SqliteBookingRepository.get_owner_user_id()` — single-column `SELECT` | changed, additive |
| `infrastructure/telegram/dialogs.py` | `DialogStep.validate` 2-arg (`text, answers`); `DialogStep.prompt` may be callable; `DialogAborted` exception | changed, additive |
| `infrastructure/telegram/register_dialog.py` | `register_booking_dialog(...)` — the 13-step `/register` `DialogDefinition` + `/register` command handler | **new** |
| `infrastructure/telegram/commands_readonly.py` | `/bookings`, `/savings`, `/checks` switched to sender-scoped queries via `UserRepository.get_by_telegram_id`; `/status` unchanged (daemon-wide) | changed |
| `infrastructure/telegram/gateway.py` | Wires `register_booking_dialog`; wraps `_reply` in a per-chat `RateLimiter` (`limits.messages_per_minute_per_chat`) | changed, additive block |
| `infrastructure/notifications/routing.py` | `resolve_telegram_chat_id(user, telegram_bot_settings)`, `OwnerBookingNotifierResolver` (a `NotifierResolver`) | **new** |
| `monitor/user_limits.py` | `DailyCounter`, `CheckPlan`, `build_check_plan(...)`, `users_needing_capped_notice(...)` — all pure, no I/O | **new** |
| `monitor/search_check_job.py` | `BookingComSearchMonitor.run_all_active(bookings: list[Booking] \| None = None)` — override param, default unchanged | changed, additive |
| `cli/commands.py` | `_make_check_job`: builds `DailyCounter`s once per daemon start, computes `build_check_plan` each tick, records skipped-check history rows, sends once-daily capped notices, passes the ordered plan to `run_all_active`, wires `OwnerBookingNotifierResolver` as the pipeline's resolver; `_SAMPLE_CONFIG`/`cmd_config_show` gain `[limits]` | changed |

## `/register` dialog design (US-025)

13 steps, one field each, each `validate` constructing the real domain value object and
surfacing its `ValueError` verbatim:

```
property_name -> property_ref (skip='-') -> check_in -> check_out (cross-field: StayDates)
  -> room_type -> baseline_price ("AMOUNT CUR") -> refundable (no -> DialogAborted)
  -> refund_note (skip='-') -> refund_deadline (skip='-') -> occ_adults -> occ_children
  -> occ_rooms -> confirmation_id -> confirm (dynamic summary prompt; no -> DialogAborted)
```

`on_complete` re-resolves the sender and re-checks the booking cap (closing the
dialog-duration race), then calls the same `register_booking()` application function
`cmd_register` calls, with `user_id=sender.user_id`. A skipped `property_ref` falls back to
the property name (`Property.booking_com_ref` requires non-empty; the CLI requires
`--property-ref` explicitly, the dialog makes it optional by design — documented in
`bolt.md`).

`/register`'s command handler (not a dialog step) checks the cap *before* even calling
`dialog_manager.start()`, so an already-capped user never enters the dialog at all.

## Sender-scoped read commands (US-025 AC / US-029)

`commands_readonly.py` adds `_resolve_active_user(store, telegram_user_id)` — a thin
`UserRepository.get_by_telegram_id` call, `None` unless `is_active`. `/bookings` and
`/savings` then call `list_active_for_user`/`list_all_for_user` instead of the unscoped
list methods. `/checks <id>` additionally checks `get_owner_user_id(id) == sender.user_id`
before returning history — a mismatch (including a genuinely unknown id) returns the exact
same "No checks recorded for booking '<id>'." message, so a user can't probe for other
users' booking ids by comparing error text.

Admission (whether a sender ever reaches a handler at all) stays bolt 009's `access.py`
concern; this bolt only decides what a reached, resolved sender is allowed to see.

## Alert routing (US-030)

```
NotificationDispatcher(resolver=OwnerBookingNotifierResolver(...))
  .dispatch(opportunity, booking)
    -> notifiers = resolver(booking)
    -> booking_repo.get_owner_user_id(booking.booking_id)
    -> user_repo.get_by_id(owner_user_id)
    -> user.is_owner?  -> static owner_notifiers (email + configured telegram_chat_id, unchanged)
       : user.is_active? -> resolve_telegram_chat_id(user, telegram_bot_settings)
                              -> [TelegramNotifier(token, chat_id=str(chat_id))]
                            else -> [] (revoked/unreachable/no token; warning logged)
```

`resolve_telegram_chat_id` prefers `user.telegram_user_id`; for an owner with none set
(laptop-mode default), it falls back to `telegram_bot_settings.owner_chat_id` — the only
place a VPS-deployed owner's chat id is configured today. `NotificationDispatcher.dispatch`
already treats an empty notifier list as "nothing configured" (pre-existing behavior), so a
booking with an unreachable owner is a warning, not a pipeline failure.

## Fair scheduling + limits (US-031)

`_make_check_job` builds `checks_today`/`capped_notice_sent_today` (`DailyCounter`) once,
outside the returned `_job` closure, so they live for the daemon process (in-memory,
UTC-midnight rollover — see `bolt.md` notes for the restart-loses-today's-counts
trade-off). Each tick:

```
users = user_repo.list_active()
bookings_by_user = {u.user_id: booking_repo.list_active_for_user(u.user_id) for u in users}
plan = build_check_plan(users, bookings_by_user, checks_today.snapshot(), limits.max_checks_per_user_per_day)
  -> plan.ordered: [(user_id, booking), ...] round-robin across eligible users
  -> plan.capped_user_ids: users excluded this tick

for capped_user_id in plan.capped_user_ids:
    record a USER_CHECK_LIMIT_REACHED check-history row per their skipped booking

for capped_user_id in users_needing_capped_notice(plan.capped_user_ids, capped_notice_sent_today):
    send one "daily limit reached" Telegram message (best-effort; warns on failure)

results = monitor.run_all_active(bookings=[b for _uid, b in plan.ordered])
for user_id, _booking in plan.ordered:
    checks_today.increment(user_id)
```

`build_check_plan` interleaves round-robin (user A's 2nd booking checked before user B's
3rd) rather than concatenating per-user queues, so one user's many/slow bookings can't push
another user's checks to the back of a tick.

## Rate limiting (US-031)

`gateway.py` wraps `_reply` in a `RateLimiter(max_events=limits.messages_per_minute_per_chat,
window_seconds=60.0)` (reusing bolt 008's generic `access.RateLimiter`, not modifying
`access.py`). A breach logs and drops the send — never raises, never queues, never spams
further.

## LLM daily-call ceiling (US-031, partial)

`limits.max_llm_calls_per_user_per_day` is validated and available on `Config`, but no
enforcement point wires it into `BookingComSearchMonitor` this bolt — see `bolt.md` "Notes"
for why (a single shared LLM extractor/agent-brain per tick, not per booking, makes a clean
per-user suppression a larger change than this bolt's scope). Left explicit rather than
silently unimplemented.
