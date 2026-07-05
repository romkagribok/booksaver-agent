---
unit: 002-agentic-escalation
bolt: 007-agentic-escalation
stage: design
status: complete
updated: 2026-07-06T00:25:00Z
---

# Technical Design — Agentic Escalation

> Scope: US-020, US-021, US-022. Runtime deps stay playwright + anthropic — the agent
> loop is a plain tool-use loop on the anthropic SDK, no agent frameworks (ADR-016).

## Module Map

| Module | Role | New/Changed |
|--------|------|-------------|
| `domain/agent.py` | `AgentActionType`, `AgentAction`, `ElementInfo`, `Observation`, `AgentBudget` (+`BudgetExceeded`), `GuardRule`/`ActionGuard` (pure), `TraceEvent`, `CheckTrace` | **new** |
| `domain/check_result.py` | + `FailureCode.{AGENT_GAVE_UP, BLOCKED_ACTION, BUDGET_EXCEEDED}`; + `ExtractionMethod.AGENT` | changed |
| `domain/models.py` | `Config` + `agent_settings: AgentSettings` (max_steps, max_llm_calls, check_timeout_seconds) | changed |
| `application/ports.py` | + `AgentBrain` Protocol; `InteractiveBrowser` + `observe()`, `act()`, `screenshot()`; + `CheckTraceRepository` | changed |
| `application/load_config.py` | `[agent]` section parsing + validation (positive ints, sane bounds; defaults 15/20/180) | changed |
| `monitor/browser_agent.py` | `BrowserAgent.complete_step()` — the escalation loop: observe (tier 1) → brain.decide → guard → act → re-verify; auto tier-2 after 2 failed actions or on `request_screenshot`; budget consumed per turn (screenshot turns ×2) | **new** |
| `monitor/trace.py` | `TraceRecorder` accumulating `TraceEvent`s; snapshot writer with rotation (max 20 files / 10 MB total, 0600) | **new** |
| `monitor/search_journey.py` | `SearchJourney(browser, escalator=None)`: on step exception → `escalator.complete_step(...)`; agent success continues to the next step; give-up/blocked/budget map to their failure codes. Verification helpers per step (`_verify_step_done`) so agent success is checked, not assumed | changed |
| `monitor/search_check_job.py` | Builds `BrowserAgent` when LLM configured; passes budget + trace recorder; marks `ExtractionMethod.AGENT` on agent-assisted successes; persists trace for every check; wall-clock deadline checked between steps | changed |
| `infrastructure/browser/playwright_adapter.py` | `observe()`: enumerate `a, button, input, select, textarea, [role=button]` (visible, capped ~120) into `ElementInfo` refs `e0..eN` (ref map kept until next observe); `act()`: dispatch AgentAction via the ref map; `screenshot()`: viewport PNG bytes | changed |
| `infrastructure/llm/anthropic_adapter.py` | `AnthropicAgentBrain` — tool-use loop: one `messages.create` per turn with tools click/fill/select/scroll/extract/request_screenshot/give_up; observation rendered as text block (+image block on tier 2); malformed/absent tool call → treated as give_up with reason | **changed/new class** |
| `infrastructure/persistence/schema.sql` + `sqlite_store.py` | v6: `check_traces` table (additive); `SqliteCheckTraceRepository` | changed |
| `cli/commands.py` | `checks trace <check-id>` renders the trace; `checks list [--booking]` helper to find check ids; `[agent]` sample config section | changed |

## The Escalation Loop (US-020)

```
scripted step raises
  └─ escalation_started(step, reason) → trace
     loop while budget allows:
       observation = browser.observe()            # tier 1: url, title, text, elements
       if tier2_pending: observation += screenshot; budget.consume(2) else consume(1)
       action = brain.decide(goal, observation, history)   # 1 LLM call, budgeted
       if action is give_up  → StepOutcome.failed(AGENT_GAVE_UP reason)
       if action is request_screenshot → tier2_pending = True; continue
       guard.check(action, observation)            # blocked → trace + inform brain, retry
       browser.act(action)                          # unknown ref → failed action, retry
       guard.check_url(browser.observe().url)       # landed on denylist → BLOCKED_ACTION
       if step_verified(step): return StepOutcome.success (agent-assisted)
       failures in a row == 2 → tier2_pending = True
```

- `history` carries the turn-by-turn actions/results so the brain doesn't repeat itself;
  it is rebuilt per step, never persisted to the LLM between checks.
- Observation text is bounded (30k chars, as extraction); element list capped at ~120
  visible interactive elements.

## Guard Rules (US-021)

Deny **click/fill/select** when the target element matches:
- label ~ `/(reserve|book now|i(')?ll reserve|confirm (booking|reservation)|pay now|complete (booking|purchase)|cancel (booking|reservation)|confirm cancellation)/i`
- href ~ `%r{/book\b|secure\.booking\.com/book|/cancel|payments?\.}`

Fail the check when the **current URL** matches the href denylist after any action
(scripted or agent). Rules live in `domain/agent.py` as data + pure functions; the
adapter (`act()`) and the loop both consult them — the prompt also states the policy,
but enforcement never relies on the prompt.

## Config (US-021)

```toml
[agent]
max_steps = 15              # agent turns per check (screenshot turns count double)
max_llm_calls = 20          # all LLM calls in one check (agent + extraction)
check_timeout_seconds = 180 # wall-clock per booking check
```
Validation: ints ≥ 1; timeout 30–3600; defaults applied when the section is absent.
LLM extraction calls from bolt 006 (`extract_offers`) draw from the same
`max_llm_calls` budget.

## Traces & Snapshots (US-022)

- `check_traces` row per check: `trace_json` = ordered events. Written even for
  scripted-only checks (journey outcomes + result) so `checks trace` always answers.
- Failure snapshots: `{data_dir}/snapshots/{check_id}.txt` (page text) and `.png`
  (only when a screenshot was already taken for the agent — never captured extra for
  snapshots). Rotation keeps newest 20 files and ≤ 10 MB total; files chmod 0600.
- Redaction: events store selectors, refs, labels, URLs, reasons — never cookie
  values; the snapshot writer refuses content containing the session cookie header
  pattern (tested).

## Testing Strategy (stage 5 preview)

- `FakeAgentBrain` emitting scripted action sequences → loop tests: success after N
  actions, give-up, unknown ref retry, blocked action then alternative, screenshot
  request (tier 2, double budget), budget exhaustion mid-loop.
- Guard unit matrix: labels/hrefs/URLs blocked vs allowed (room links, policy links
  allowed; reserve/cancel/checkout blocked).
- Budget math: step costs, llm-call coupling with extract_offers, wall-clock via
  injected clock.
- Journey + escalator integration: scripted failure → agent completes → journey
  continues; agent-assisted success marked `agent`; give-up/blocked/budget codes.
- Trace: event ordering, persistence round trip, `checks trace` CLI rendering,
  snapshot rotation + redaction guard.
- `AnthropicAgentBrain` parsing: tool-call → AgentAction mapping, malformed reply →
  give_up (fake SDK objects, no network).
