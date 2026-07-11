---
unit: 003-conversational-booking-ops
bolt: 010-conversational-booking-ops
stage: model
status: complete
updated: 2026-07-11T18:40:00Z
---

# Domain Model — Conversational Booking Ops

> Scope: Bolt `010-conversational-booking-ops` — **US-025** (`/register` dialog),
> **US-030** (alert routing), **US-031** (per-user limits + fair scheduling). Builds on
> bolt 008's Telegram gateway (`CommandRouter`, `DialogManager`) and bolt 009's users
> table/scoped repositories. No new domain rules for booking registration itself — this
> bolt is an inbound adapter (the dialog) plus two application-layer concerns (alert
> routing, fair scheduling), all reusing existing value objects (ADR-004).

## Bounded Context

This bolt spans three small contexts that share one theme — per-user fairness — but are
independently testable:

1. **Registration dialog** (`infrastructure/telegram/register_dialog.py`) — an inbound
   adapter collecting a `Booking` one field at a time via the existing `DialogManager`,
   validated with the same value objects `cli/commands.py:cmd_register` uses, ending in a
   call to the existing `register_booking` application service.
2. **Alert routing** (`infrastructure/notifications/routing.py`) — resolves a booking to
   its owning user's reachable Telegram chat, given the existing `Notifier` protocol.
3. **Fair scheduling / limits** (`monitor/user_limits.py`, `domain/value_objects.py`
   `LimitsSettings`) — pure functions over `User`/`Booking` sequences deciding per-tick
   check order and daily notice timing.

## Value Objects

| Value Object | Properties | Constraints |
|--------------|------------|-------------|
| **LimitsSettings** | `max_bookings_per_user` (int, default 3), `max_checks_per_user_per_day` (int, default 48), `max_llm_calls_per_user_per_day` (int, default 200), `messages_per_minute_per_chat` (int, default 20) | Every field must be `>= 1`; validated at construction and again at `load_config` |
| **CheckPlan** | `ordered: list[tuple[user_id, Booking]]`, `capped_user_ids: list[int]` | `ordered` interleaves round-robin across users; `capped_user_ids` lists users excluded entirely this tick |

## Dialog Framework Extensions (ADR: none needed — additive to bolt 008's framework)

| Extension | Why |
|-----------|-----|
| `DialogStep.validate: (text, answers_so_far) -> str \| None` | `check_out > check_in` needs the already-answered `check_in` — the sole cross-field rule this dialog needs, expressed via the real `StayDates` value object |
| `DialogStep.prompt: str \| (answers_so_far) -> str` | The final confirmation step's prompt is the dynamic full summary |
| `DialogAborted(message)` exception | A "no" answer (refundability, final confirm) ends the whole dialog with a specific message instead of re-prompting the current step |

## Entities / Services (non-persistent, process-lifetime)

| Type | Role | Constraints |
|------|------|-------------|
| **register_booking_dialog(...)** | Builds the `/register` `DialogDefinition` (13 steps) and registers it on the router | Resolves the sender via `UserRepository.get_by_telegram_id`; unresolved/revoked sender or over-cap gets a polite refusal, dialog never starts |
| **OwnerBookingNotifierResolver** | `Booking -> list[Notifier]`, used as `NotificationDispatcher`'s `resolver` | Owner-owned bookings keep the static email+Telegram list; other users route to a fresh `TelegramNotifier` at their own chat; unreachable owner logs a warning and sends nothing |
| **DailyCounter** | In-memory per-key counter, UTC-midnight rollover | Process-lifetime only; a restart loses today's counts (documented trade-off) |
| **build_check_plan(...)** | Pure function: users + their bookings + today's counts + cap -> `CheckPlan` | Users at/over the daily cap are excluded entirely, not truncated |
| **users_needing_capped_notice(...)** | Pure function: capped user ids + notice-sent counter -> ids due a notice this tick | Marks returned ids as notified (side effect), so a tick calling it twice never double-notifies |

## Domain Rules

1. **Same validation, no duplication** (US-025 AC): every dialog step validates by
   constructing the real domain value object (`Property`, `StayDates`, `RoomType`,
   `Money`, `ConfirmationId`, `Occupancy`) and surfacing its `ValueError` message verbatim
   — a rule change to a value object automatically propagates to both the CLI and the
   dialog.
2. **Refundable-only is a hard gate** (US-025 AC, product constraint): answering "no" to
   refundability raises `DialogAborted` with the same wording the CLI's
   `BookingRejectedError("Only refundable bookings can be registered.")` carries — nothing
   is saved.
3. **Explicit final confirmation** (US-025 AC): the last step's prompt is the full
   collected summary; only an explicit "yes" reaches `on_complete` and calls
   `register_booking`; "no" raises `DialogAborted`, safe abort.
4. **Booking scoped to the sender, owner exempt from the cap** (US-025 AC, US-029): a
   completed dialog calls `register_booking(..., user_id=sender.user_id)` — the CLI's
   pre-multi-user default (`user_id=None` -> owner) is untouched. The active-booking cap
   (`limits.max_bookings_per_user`) is checked at dialog start (fail fast) and again at
   save (closes a race with a concurrent registration); the owner is exempt.
5. **No cross-user data leakage** (US-025 AC, US-029): `/bookings`, `/savings`, `/checks`
   resolve the sender and query only `list_active_for_user`/`list_all_for_user`/an
   ownership check by id — never the unscoped `list_active()`/`list_all()`. `/checks` on
   another user's booking id returns the identical "not found" message as a genuinely
   unknown id (no oracle).
6. **Alert routed to exactly one owner** (US-030 AC): `OwnerBookingNotifierResolver`
   resolves booking -> owning `user_id` -> `User` -> reachable chat id exactly once per
   dispatch; a booking never fans out to more than its owner's channels.
7. **Fair, capped, once-a-day-polite scheduling** (US-031 AC): `build_check_plan`
   round-robins active users' bookings so no user's queue can push another's to the back
   of a tick; a user at today's ceiling is excluded from the tick's bookings entirely (a
   `USER_CHECK_LIMIT_REACHED` check-history row is still recorded per skipped booking) and
   notified once per calendar day via `users_needing_capped_notice`, not every tick.
8. **Breaches are polite, never silent, never fatal** (US-031 AC): booking-cap and
   daily-check-cap breaches produce a chat message; outbound message-rate-limit breaches
   degrade to drop+log (a chat that's already flooding shouldn't get another message); an
   unreachable notification target logs a warning and the pipeline continues to the next
   booking.
