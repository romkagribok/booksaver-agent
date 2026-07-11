---
unit: 001-telegram-bot-gateway
bolt: 008-telegram-bot-gateway
stage: model
status: complete
updated: 2026-07-11T17:45:00Z
---

# Domain Model — Telegram Bot Gateway

> Scope: Bolt `008-telegram-bot-gateway` — **US-023** (update loop), **US-024** (router +
> dialogs), **US-036** (read-only inspection). Owner-only guard; multi-user access modes
> are unit 002. No domain logic lives in this bounded context — it is a pure inbound
> adapter over existing application services/repositories (ADR-004).

## Bounded Context

**Telegram Bot Gateway** is an inbound adapter wrapping the daemon. It owns:

1. **Transport** — long-polling the Telegram Bot API and turning raw updates into typed
   commands.
2. **Routing** — dispatching a typed command to a registered handler, or a message to an
   active per-chat dialog.
3. **Access** — resolving every update to a sender chat id and enforcing owner-only access
   with a rate-limited refusal.
4. **Read projections** — formatting existing repository data (bookings, savings, checks,
   scheduler status) into chat-sized replies.

It explicitly does **not** own booking registration, savings evaluation, or rebook
confirmation logic — those stay in `application/` and are only *called from* future bolts'
dialog handlers registered on this gateway's router.

## Value Objects

| Value Object | Properties | Constraints |
|--------------|------------|-------------|
| **TelegramBotSettings** | `enabled` (bool), `owner_chat_id` (int \| None), `poll_timeout_seconds` (int) | `owner_chat_id` required when `enabled`; `poll_timeout_seconds` clamped to 25-50 at load time, validated as a hard bound at construction |
| **IncomingCommand** | `user_id`, `chat_id`, `command`, `args`, `raw_text` | Resolved from an update's `message.from.id`/`message.chat.id` — unforgeable via the Bot API (not derived from message content) |
| **DialogStep** | `key`, `prompt`, `validate: str -> str \| None` | `validate` returns `None` for acceptance or an error message to re-prompt with |
| **DialogDefinition** | `name`, `steps: tuple[DialogStep, ...]`, `on_complete: (user_id, chat_id, answers) -> str` | Must have >= 1 step |

## Entities / Services (non-persistent, process-lifetime)

| Type | Role | Constraints |
|------|------|-------------|
| **TelegramBotClient** | urllib+certifi wrapper for `getUpdates`/`sendMessage`/`editMessageText`/`answerCallbackQuery`/`deleteMessage` | Injectable transport for tests; never touches the network in the test suite |
| **TelegramOffsetStore** | Persists the last-processed update offset to a plain file in the data dir | Mirrors `LocalSessionRepository`'s pattern; 0600 permissions; corrupt/missing file treated as "no offset" |
| **CommandRouter** | Registry: `command string -> handler`; `dispatch()` returns whether a handler existed | Registry API so units 2-4 register their own commands without gateway changes |
| **DialogManager** | At most one active `DialogDefinition` per chat id; advances/validates/completes/cancels | In-memory only (process lifetime) — a restart resets an in-progress dialog rather than replaying or crashing it |
| **OwnerGuard** | `is_owner(chat_id)`, `should_send_refusal(chat_id)` (rate-limited) | Backed by a generic `RateLimiter` (sliding window, per-key) |
| **BotLoop** | The update loop itself: fetch -> access-guard -> route/dialog -> advance+persist offset | Runs as a thread; a slow/failed price check never delays replies (its own SQLite connection, WAL mode, no browser) |

## Domain Rules

1. **Owner-only, silent-after-one** (FR-2 subset for this bolt): every update resolves to
   a chat id; only the configured `owner_chat_id` may reach the router or any dialog. A
   non-owner chat gets exactly one refusal per rate-limit window, then nothing — no state
   change, no LLM call, ever.
2. **Offset durability** (US-023 AC): the offset is advanced only after a batch is fully
   processed and is persisted before the next long-poll call. A crash mid-batch replays
   that batch on restart (at-least-once, never at-most-zero); handlers here are read-only
   or idempotent (register/cancel a dialog), so replay is safe in this bolt.
3. **Dialog re-prompt on invalid input** (US-024 AC): a step's `validate` failing never
   advances `step_index` — the same prompt (with the error) is shown again.
4. **`/cancelflow` from any step** (US-024 AC): cancellation does not consult the active
   step at all; it simply removes the chat's entry from `DialogManager`.
5. **No domain logic in the bot layer** (US-024 AC, ADR-004): every read-only handler in
   `commands_readonly.py` only calls existing repositories (`SqliteBookingRepository`,
   `SqliteCheckHistoryRepository`, `SqliteSavingsRepository`) and formats text — the same
   repositories the CLI (`cli/commands.py`) already uses.
6. **Fail-fast watchdog** (US-023 AC): an unhandled exception in either the scheduler loop
   or the bot loop stops the other (`scheduler.request_stop()`) and the daemon process
   exits nonzero once both threads have joined — no half-alive daemon for
   systemd/Docker's restart policy to catch.
