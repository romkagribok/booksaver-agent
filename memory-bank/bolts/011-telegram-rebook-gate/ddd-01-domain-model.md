---
unit: 004-telegram-rebook-gate
bolt: 011-telegram-rebook-gate
stage: model
status: complete
updated: 2026-07-11T20:00:00Z
---

# Domain Model — Telegram Rebook Gate

> Scope: Bolt `011-telegram-rebook-gate` — **US-032** (Telegram `ConfirmationGate` +
> audit), **US-033** (device-handoff deep link + outcome follow-up). No new domain rules:
> this bolt is entirely inbound-adapter work over intent 001 unit 004's existing
> `ConfirmationGate`/`Navigator` ports and `RebookSession` state machine (ADR-004,
> hexagonal). `domain/rebook.py` and `application/rebook_service.py` are read-only
> dependencies here, not modified.

## Bounded Context

One new adapter module, `infrastructure/telegram/rebook_gate.py`, spanning three
cooperating concerns:

1. **Blocking confirmation bridge** — a worker thread runs the synchronous
   `RebookSessionService.run()`; the bot loop thread (on a matching `callback_query`)
   resolves the pending prompt the worker is parked on. `PendingPromptRegistry` +
   `wait_with_shutdown` are the only shared mutable state between the two threads.
2. **`TelegramConfirmationGate`** — the `ConfirmationGate` port adapter: one
   inline-keyboard prompt per `ask()` call, fail-safe decline on timeout/shutdown/no,
   additive audit event per answer.
3. **`TelegramNavigator` + outcome follow-up** — the `Navigator` callback adapter: sends
   a deep link instead of opening a browser, then (after the session ends) asks whether
   each handed-off step was actually completed.

## Value Objects / Data Carriers (new, all in `rebook_gate.py`; none touch `domain/`)

| Type | Properties | Constraints |
|------|------------|-------------|
| **`_PendingPrompt`** | `chat_id`, `user_id`, `message_id`, `event: threading.Event`, `approved: bool \| None` | `approved` stays `None` until resolved exactly once; `event` is set exactly once |
| **`IncomingCallback`** (in `router.py`, reused, not rebook-specific) | `user_id`, `chat_id`, `callback_query_id`, `message_id`, `data` | Mirrors `IncomingCommand`'s shape for the callback_query update type |

## Entities / Services (process-lifetime, not persisted)

| Type | Role | Constraints |
|------|------|-------------|
| **`PendingPromptRegistry`** | nonce -> `_PendingPrompt` map | Thread-safe (single lock); `resolve()` matches nonce **and** chat_id **and** user_id — any mismatch is a no-op, not an error; a nonce is used at most once (`discard()`d after `ask()` returns regardless of outcome) |
| **`TelegramConfirmationGate`** | `ConfirmationGate.ask()` implementation | Only an explicit `"yes"` tap sets `approved=True`; timeout, shutdown, `"no"`, or a mismatched tap all decline; edits the sent message after resolving so it cannot be tapped twice |
| **`_SessionIdCapturingRepo`** | Wraps the injected `RebookSessionRepository` | Delegates every call unchanged; only observes `add(session)` to learn `session.session_id` into a shared `dict` box — the sole reason it exists, since `ConfirmationGate.ask()` is never given the session |
| **`TelegramNavigator`** | `Navigator` callback (`(url, description) -> None`) | Called exactly twice by the service, in a fixed order (cancel, then book — guaranteed by the state machine); relays the service's own URL for the first call, substitutes `build_deep_link_url(booking)` for the second; never touches a browser |
| **`_ActiveSessionGuard`** | `set[int]` of local `user_id`s with a running session | `try_acquire`/`release`; a second `/rebook` for an already-active user_id is refused before any thread is spawned |
| **`build_deep_link_url(booking)`** | Pure function -> URL | Same param names as `search_journey._search_results_url` (`ss`, `checkin`, `checkout`, `group_adults`, `group_children`, `no_rooms`) so the link reaches the same verified property |
| **`run_outcome_followup(...)`** | Post-session pure orchestration | Asks one completed/abandoned question per handoff actually sent (`navigator.cancel_handoff_sent`/`book_handoff_sent`), in order; each answer (or timeout) appends one `rebook_events` row |

## Domain Rules

1. **The state machine is authoritative and untouched** (US-032 AC, frozen surface):
   `TelegramConfirmationGate` only ever returns a `ConfirmationAnswer`; it cannot skip a
   gate, reorder a transition, or execute an action — those remain exclusively
   `RebookSessionService.run()`'s job, identical to the CLI path.
2. **Explicit yes only** (US-032 AC): mirrors `ConfirmationAnswer.from_input`'s existing
   fail-safe contract — the gate never infers approval from anything but the literal
   `"yes"` branch of a resolved prompt.
3. **Only the addressed user's tap counts** (US-032 AC): `PendingPromptRegistry.resolve`
   requires an exact `(chat_id, user_id)` match to the prompt's origin; a tap from any
   other chat or Telegram user is silently ignored (the pending prompt stays pending).
4. **Timeout and shutdown both fail safe** (US-032 AC): `wait_with_shutdown` returns
   `False` for either a real timeout or a set `stop_event`; both branches decline exactly
   like a "no" tap, so a hung daemon or reboot never leaves an ambiguous, appearing-approved
   state.
5. **Audit is additive, not a schema change** (US-032 AC): each resolved prompt appends
   one extra `rebook_events` row (via the real `RebookEventRepository`, `session_id`
   recovered via `_SessionIdCapturingRepo`) carrying `channel=telegram`, `chat_id`,
   `message_id`, and an ISO-8601 timestamp packed into the existing free-text `detail`
   column — no new table, no new column, `SCHEMA_VERSION` unchanged.
6. **One session per user** (US-032 AC): `_ActiveSessionGuard` is checked and acquired
   before any thread starts, and released in a `finally` regardless of how the session
   ends (completed, declined, or an unexpected exception) — a crash can never leave a user
   permanently locked out of `/rebook`.
7. **Ownership gates access before any confirmation is even asked** (US-032 AC): `/rebook
   <id>` resolves the sender's local user, the opportunity's booking's owning user
   (`UserRepository.get_owner_of_booking`), and refuses with the *same* message used for a
   genuinely unknown id when they don't match — no existence oracle for opportunities
   belonging to someone else.
8. **The deep link reproduces the opportunity's identity** (US-033 AC): property name,
   check-in, check-out, and (when known) adults/children/rooms are always present in the
   link sent for the "book" step — never the plain `_rebook_url` the service builds
   internally (which lacks occupancy).
9. **The VPS browser performs no cancel/book navigation** (US-033 AC, ADR-012/ADR-016):
   `TelegramNavigator.__call__` only ever calls `client.send_message` — it holds no
   `InteractiveBrowser`/`BrowserSession` reference at all, so it is structurally
   incapable of driving the browser regardless of what URL it's given.
10. **Unreported outcomes are told apart from unset ones** (US-033 AC):
    `run_outcome_followup` always appends an event for every handoff that was sent —
    `status=completed`, `status=abandoned`, or (no answer within the timeout)
    `status=unreported` — so the rebook log never conflates "never asked" with "asked and
    ignored."
