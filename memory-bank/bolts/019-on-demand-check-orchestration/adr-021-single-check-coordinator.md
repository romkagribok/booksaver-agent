# ADR-021: One coordinator serializes scheduled and on-demand checks

- **Status**: accepted
- **Date**: 2026-07-18
- **Bolt**: 019-on-demand-check-orchestration (on-demand-check-orchestration)
- **Amends**: ADR-008 synchronous scheduler ownership and ADR-017 budgeting scope

## Context

The daemon originally had one synchronous scheduled check closure, so sequential browser execution
was an accidental property of the scheduler thread. Adding Telegram-triggered checks creates a second
requesting thread. Reproducing the closure there would create separate daily counters, duplicate
monitor/savings wiring, competing Playwright browsers, and a way to bypass per-user limits. The
configured daily LLM-call ceiling also existed as configuration but was not enforced by the original
closure.

## Decision

1. One daemon-lifetime `CheckCoordinator` is the only admission and orchestration boundary for
   scheduled and on-demand price checks.
2. A non-blocking process-local gate permits one browser batch at a time. A busy scheduled tick skips;
   a busy manual request receives an immediate retry-later response. Work is not queued.
3. Telegram browser work runs on a daemon background thread so long polling remains responsive. The
   worker observes the scheduler's shared stop event and re-resolves active user, booking ownership,
   and booking status before execution and completion disclosure.
4. Both entry points use the same monitor, session handling, trace/history/failure tracking, savings
   pipeline, personal-key resolution, owner notifier routing, and invalid-key notice path.
5. Thread-safe in-memory UTC-day counters are shared by both paths. Check allowance is reserved when
   execution begins. Scheduled planning is clipped to the user's remaining allowance.
6. Actual LLM calls are reported by the per-check budget and added to the booking owner's daily
   counter. The per-check cap is reduced to the remaining daily allowance. At zero remaining calls,
   the real browser check still runs in scripted/DOM-only mode.
7. Counters retain US-031's safety-net semantics: daemon restart resets them; no persistence migration
   is introduced.

## Alternatives considered

- **A second scheduler or Telegram-specific monitor**: duplicates core behavior and can race the
  scheduled browser. Rejected.
- **Queue manual requests**: can execute stale requests minutes later, complicates shutdown, and makes
  duplicate taps surprising. Rejected.
- **Block Telegram until Playwright completes**: freezes polling and callback handling for potentially
  several minutes. Rejected.
- **Reject checks after daily LLM exhaustion**: wastes robust scripted/DOM behavior and conflates a
  check allowance with an optional interpretation allowance. Rejected.
- **Multiple concurrent browsers**: increases Booking.com/IP pressure, memory cost, and SQLite/session
  coordination risk for little benefit in a personal daemon. Rejected.

## Consequences

- Immediate checks behave exactly like scheduled checks and can create ordinary traces, history,
  savings, and proactive alerts.
- Manual checks cannot bypass cost limits or overlap scheduled navigation.
- A manual request can receive “busy” even when it targets a different booking; this is the explicit
  reliability/cost trade-off for a single owner-operated process.
- Long browser work does not block Telegram, while shutdown remains bounded because worker threads are
  daemonized and no new work is admitted after the shared stop event is set.
