# Construction Log: Conversational Booking Ops

**Intent:** `003-telegram-interface`
**Unit:** `003-conversational-booking-ops`
**Status:** Complete

## Bolt 010 — 2026-07-11T18:30:00Z → 2026-07-11T19:46:16Z

Delivered US-025 (`/register` chat dialog), US-030 (savings alerts routed to the booking
owner's own chat), and US-031 (per-user booking cap, per-user daily check ceiling with
fair round-robin scheduling, per-chat outbound message rate limiting, and an in-memory
per-user daily LLM-call counter).

- **Stages**: model → design → implement → test, all complete (see
  `memory-bank/bolts/010-conversational-booking-ops/`).
- **Result**: 504/504 tests passing (45 new), ruff clean, mypy clean.
- **New modules**: `infrastructure/telegram/register_dialog.py` (`/register` dialog),
  `infrastructure/notifications/routing.py` (`OwnerBookingNotifierResolver`,
  `resolve_telegram_chat_id`), `monitor/user_limits.py` (`DailyCounter`, `build_check_plan`,
  `users_needing_capped_notice`).
- **Changed**: `infrastructure/telegram/dialogs.py` (2-arg `validate`, callable `prompt`,
  `DialogAborted` — additive extensions bolt 011 can also use),
  `infrastructure/telegram/commands_readonly.py` (`/bookings`/`/savings`/`/checks`
  sender-scoped), `infrastructure/telegram/gateway.py` (register-dialog wiring + per-chat
  rate limiting), `application/savings_pipeline.py` (`NotificationDispatcher` optional
  `resolver`), `application/load_config.py` (`[limits]` parsing), `application/ports.py`
  (`BookingRepository.get_owner_user_id`), `domain/value_objects.py` (`LimitsSettings`),
  `domain/models.py` (`Config.limits_settings`), `domain/check_result.py`
  (`FailureCode.USER_CHECK_LIMIT_REACHED`), `infrastructure/persistence/sqlite_store.py`
  (`get_owner_user_id`, additive read — no schema/version change),
  `monitor/search_check_job.py` (`run_all_active(bookings=...)` override, default
  unchanged), `cli/commands.py` (`_make_check_job` fair scheduling + alert routing wiring,
  `_SAMPLE_CONFIG`/`config show` gain `[limits]`).
- **Not touched** (coordination with the parallel bolt-009 worker): `access.py`,
  `pyproject.toml`, LLM key resolution/`LLMClientFactory`, invite codes, `/setkey`/`/admin`,
  `SCHEMA_VERSION` (stays 7).

Completion criteria met: a brand-new user's `/register` produces the same `Booking`
aggregate the CLI would, scoped to them; refundable-only / hotels-only rejections use the
CLI's own messages via the shared value objects; a savings alert reaches only the owning
user's chat; limit breaches are polite (a chat message) or a graceful drop+log (message
rate limiting), never silence and never a crash.

## Documented follow-ups (not this bolt's scope)

- `limits.max_llm_calls_per_user_per_day` is validated and tracked in config but not yet
  enforced against the shared per-tick LLM extractor/agent-brain — see `bolt.md` notes.
- The daily-limit in-memory counters (`DailyCounter`) reset on a daemon restart; a small
  additive counter table is a clean follow-up if daemon uptime proves too short in practice.
- Sender resolution for `/register` and the scoped read commands assumes bolt 009's
  admission flow links a sender's `telegram_user_id` to a `users` row (including the
  owner's, for a VPS deployment) before a command handler runs — reconcile at merge if
  bolt 009's `access.py` does this differently.

## Next

Unit `004-telegram-rebook-gate` (bolt 011) builds the Telegram `ConfirmationGate` and
device-handoff deep link, reusing this bolt's `DialogAborted`/dynamic-prompt extensions to
`dialogs.py`.
