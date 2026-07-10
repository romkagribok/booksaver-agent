---
unit: 002-agentic-escalation
bolt: 007-agentic-escalation
stage: model
status: complete
updated: 2026-07-06T00:20:00Z
---

# Domain Model — Agentic Escalation

> Scope: Bolt `007-agentic-escalation` — **US-020** (agent step takeover), **US-021**
> (action guard + hard caps), **US-022** (traces + inspection). Builds on bolt 006's
> journey step seams. No source code in this stage.

## Bounded Context

**Agentic Escalation** wraps the Search Journey context. It owns:

1. **The agent loop** — when a scripted step fails, an LLM decides bounded browser
   actions from tiered observations until the step goal is met or it gives up.
2. **Safety** — an action guard that keeps every automated action read-only on the
   account, and hard budgets that bound each check's cost.
3. **Diagnosability** — an ordered trace of every check and rotated failure snapshots,
   all local.

## Value Objects

| Value Object | Properties | Constraints |
|--------------|------------|-------------|
| **AgentActionType** | enum: `click`, `fill`, `select`, `scroll`, `extract`, `request_screenshot`, `give_up` | The complete action vocabulary (FR-3); nothing else reaches the browser |
| **AgentAction** | `type`, `ref` (element reference, for click/fill/select), `value` (fill/select text, scroll direction, extract payload, give-up reason) | `ref` must come from the current observation's element list — stale/unknown refs are rejected as failed actions, not guessed |
| **ElementInfo** | `ref` (e.g. `e7`), `role` (`link`/`button`/`input`/`select`), `label` (accessible text), `href` (links) | Enumerated fresh per observation by the browser adapter |
| **Observation** | `url`, `title`, `text` (bounded visible text), `elements` (list[ElementInfo]), `screenshot` (bytes \| None) | Tier 1 = text+elements only; tier 2 adds the screenshot (ADR-015) |
| **AgentBudget** | `max_steps` (15), `max_llm_calls` (20), `check_timeout_seconds` (180); counters `steps_used`, `llm_calls_used`, `started_at` | Config-driven, validated at load; **screenshot turns count 2 steps**; exceeding any bound aborts with `BUDGET_EXCEEDED` (ADR-017) |
| **GuardRule** | URL denylist patterns + click-label denylist patterns | Blocks reservation-mutating targets: cancellation flows, checkout/"reserve"/"book now" submission, payment pages (FR-3 safety AC) |
| **TraceEvent** | `seq`, `at`, `kind` (`journey_step`, `escalation_started`, `agent_action`, `agent_blocked`, `screenshot_tier`, `agent_result`, `check_result`), `detail` | Append-only; credentials/cookies never appear in details |
| **CheckTrace** | `check_id`, `booking_id`, `created_at`, `events` (tuple[TraceEvent, ...]) | One per check (success or failure); persisted locally |

## Domain Rules

### Escalation (US-020)
1. Escalation triggers exactly at a failed `JourneyStep`; the agent receives the step's
   goal description and a tier-1 observation.
2. The agent may `request_screenshot` (or gets one automatically after two consecutive
   failed actions); the retried turn is tier-2 and costs 2 budget steps.
3. Agent success = the step's own verification passes when re-checked (e.g. the room
   table anchor is now present); control returns to the scripted journey at the next step.
4. `give_up` → check fails `AGENT_GAVE_UP` with step name + the agent's stated reason.
5. A successful check that used any escalation records `extraction_method = agent`
   (scripted-only checks keep `dom`/`llm`) — the US-020 scripted-vs-agent-assisted marker.

### Guard (US-021)
1. Guard is enforced **at the adapter boundary** (the last code before Playwright), not
   in the prompt: a blocked click/fill is refused, recorded as `agent_blocked`, and the
   agent is told why (it may pick another action within budget).
2. After every action, the current URL is re-checked; landing on a denylisted URL fails
   the check immediately with `BLOCKED_ACTION` (defense in depth).
3. Scripted steps pass through the same guard — no code path can act on a
   reservation-mutating target.

### Budget (US-021)
1. `steps`, `llm_calls`, and wall-clock are checked before every agent turn and between
   journey steps; first breach → `BUDGET_EXCEEDED`, daemon continues with next booking.
2. Caps live in `config.toml` `[agent]`; invalid values fail config validation with the
   same error style as existing sections.
3. Documented (ADR-017 + README): hard caps are the deliberately simple first version;
   adaptive budgeting is named future work.

### Traces (US-022)
1. Every check emits a `CheckTrace` (journey step outcomes; escalations with trigger,
   tier, actions; final result) persisted in SQLite next to check history.
2. On check failure, the current page's visible text (and the screenshot when one was
   already captured) is written under `{data_directory}/snapshots/` with rotation
   (max files + max bytes); snapshots never leave the machine.
3. Redaction rule: cookies, tokens, and env-var secrets are never placed in prompts,
   traces, or snapshots; trace persistence asserts no cookie material in event details.

## New Failure Codes

| Code | Meaning |
|------|---------|
| `AGENT_GAVE_UP` | Escalated agent chose give_up (detail: step + reason) |
| `BLOCKED_ACTION` | An action or resulting URL hit the guard denylist |
| `BUDGET_EXCEEDED` | Steps / LLM calls / wall-clock cap breached |

`ExtractionMethod` gains `AGENT = "agent"` (schema v5 already allows it).

## Domain Services

| Service | Operations | Dependencies |
|---------|------------|--------------|
| **BrowserAgent** | `complete_step(step, goal, budget, trace) -> StepOutcome` — observation → LLM decision → guarded action loop | `InteractiveBrowser` (extended), `AgentBrain` port, `ActionGuard`, `AgentBudget` |
| **ActionGuard** | `check_click(element) -> None \| Blocked`, `check_url(url) -> None \| Blocked` | pure rules |
| **TraceRecorder** | `journey_step(...)`, `escalation(...)`, `action(...)`, `finish(check_result)`; builds the `CheckTrace` | `CheckTraceRepository` port |

## Port Changes

| Port | Change |
|------|--------|
| **AgentBrain** (new) | `decide(goal, observation, history) -> AgentAction` — LLM decision per turn; anthropic tool-use adapter |
| **InteractiveBrowser** (extended) | + `observe() -> Observation` (elements enumerated with refs), `act(action: AgentAction) -> None`, `screenshot() -> bytes` |
| **CheckTraceRepository** (new) | `add(trace)`, `get(check_id)` |

## Persistence Impact

Schema **v6**: `check_traces` table (check_id UNIQUE, booking_id, created_at,
trace_json TEXT) — purely additive. Snapshot files under
`{data_directory}/snapshots/` (0600, rotated).
