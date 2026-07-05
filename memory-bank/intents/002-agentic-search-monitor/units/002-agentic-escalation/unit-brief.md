# Unit Brief: Agentic Escalation

**Unit ID:** `002-agentic-escalation`
**Intent:** `002-agentic-search-monitor`
**Status:** Planned
**Build order:** 2

## Purpose

Make the search journey survive Booking.com UI drift. When a scripted journey step fails, an LLM
browser agent takes over that step: it observes the page through tiered observations (distilled
text/DOM snapshot first, Playwright screenshot only when text is insufficient), chooses from a bounded
action vocabulary (click, fill, select, scroll, extract, give-up), acts through the existing browser
port, and hands control back to the script. An action guard makes the agent read-only on the account,
hard configurable caps bound cost per check, and every check leaves an inspectable local trace.

## Dependencies on other units

| Unit | What this unit needs |
|------|----------------------|
| `001-search-journey-monitor` (this intent) | Journey step structure with defined escalation points; step outcome reporting |
| intent-001 `002-booking-com-price-monitor` | Browser port (extended with snapshot/screenshot/element-reference operations), anthropic adapter patterns |
| intent-001 `001-core-local-data` | Config (new `[agent]` cap settings), data directory for traces/snapshots |

## Downstream consumers

- Journey checks (Unit 1) gain per-step agent takeover transparently.
- CLI gains a trace-inspection command; check history gains agent-related failure codes.

## Loose coupling / interfaces (design-level)

| Consumes | From |
|----------|------|
| Failed step context (step name, goal, page state) | search-journey-monitor |
| `BrowserSession` port operations | price-monitor infrastructure |

| Emits | To |
|-------|-----|
| Step completion or coded give-up (`AGENT_GAVE_UP`, `BUDGET_EXCEEDED`, `BLOCKED_ACTION`) | journey → CheckResult |
| Step traces + rotated failure snapshots (redacted) | local persistence + CLI |

## Recommended implementation order (within unit)

1. US-021 — Action guard + hard caps (safety rails first)
2. US-020 — Agent escalation loop with tiered observations
3. US-022 — Traces, failure snapshots, CLI inspection

---

## Story Files

- `US-020`
- `US-021`
- `US-022`

## Cross-cutting constraint

US-013 (local-only): traces and snapshots never leave the machine; LLM calls carry page content only,
never cookies/credentials. No autonomous cancel/purchase — guard enforced at the adapter level.

---

## Completion criteria (unit-level)

- A scripted-step failure triggers agent takeover; agent success resumes the journey, give-up records
  a coded failure.
- Agent cannot navigate into cancellation/checkout/payment flows (guard-tested).
- Caps (agent steps, LLM calls, wall-clock) configurable, validated, and enforced with distinct
  failure codes; docs note adaptive budgeting as future work.
- `booksaver` CLI shows a check's full step trace; failure snapshots are rotated and redacted.
