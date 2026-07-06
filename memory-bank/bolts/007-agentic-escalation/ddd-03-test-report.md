---
unit: 002-agentic-escalation
bolt: 007-agentic-escalation
stage: test
status: complete
updated: 2026-07-06T01:20:00Z
---

# Test Report — Agentic Escalation

## Summary

| Metric | Value |
|--------|-------|
| Total tests | **345 passed, 0 failed** |
| New in this bolt | 68 |
| Pre-existing (regression surface) | 277 — all green (211 MVP + 66 bolt 006) |
| Lint (`ruff check src/ tests/`) | clean |
| Types (`mypy src/`) | clean (51 files) |

## New Test Coverage by Story

### US-020 — Agent step takeover (25 tests)
- `tests/unit/monitor/test_browser_agent.py`: loop outcomes (action → verified
  success; give-up → `AGENT_GAVE_UP` with the agent's reason; unverified actions loop
  until the scripted brain runs dry); **tiered observations** — first turn is tier 1,
  `request_screenshot` delivers the image next turn, two consecutive failed actions
  auto-escalate to tier 2, `last_screenshot` retained for failure snapshots.
- `tests/unit/monitor/test_journey_escalation.py`: scripted step failure → agent
  completes the step → journey continues to success with `agent_assisted=True`;
  give-up fails the whole check; **`BOT_WALL`/auth failures are never escalated**
  (brain never consulted); scripted-only runs are not marked agent-assisted; agent
  success is postcondition-verified, not assumed (budget test exploits this).
- `tests/unit/monitor/test_agent_brain_mapping.py`: every tool call maps to its
  `AgentAction`; unknown tools (e.g. `evaluate_js`) collapse to give_up.
- `tests/unit/monitor/test_monitor_agent_wiring.py::TestAgentAssistedMarker`:
  agent-assisted success records `extraction_method='agent'`; scripted-only stays
  `dom`; no brain configured → plain `STEP_FAILED`.

### US-021 — Guard + hard caps (26 tests)
- `tests/unit/test_agent_domain.py`: `AgentSettings` validation bounds;
  `AgentBudget` step cap, **screenshot-counts-double**, LLM-call cap, wall-clock via
  injected clock; guard matrix — reserve/book-now/cancel-booking labels and
  checkout/payment/cancel hrefs+URLs blocked, room links, policy-text buttons, and
  scroll allowed.
- `tests/unit/monitor/test_browser_agent.py::TestGuardInLoop/TestBudgetsInLoop`:
  blocked click never reaches the browser and the loop continues; landing on a
  checkout URL after an action → `BLOCKED_ACTION`; step/LLM-call cap breaches →
  `BUDGET_EXCEEDED`.
- `tests/unit/test_agent_config.py`: `[agent]` section — defaults when absent,
  explicit values, partial sections, invalid values rejected with section-prefixed
  config errors.

### US-022 — Traces + inspection (17 tests)
- `tests/unit/monitor/test_trace.py`: event ordering + kinds through a full
  journey-escalation-result sequence; failure codes in the terminal event;
  **redaction** of cookie/token material in trace details and snapshot files;
  `SnapshotWriter` writes text (+png when available), rotation keeps the newest N,
  write errors never raise.
- `tests/unit/monitor/test_monitor_agent_wiring.py`: every check (success, failure,
  even pre-browser `OCCUPANCY_MISSING`) persists a trace whose last event is the
  check result; escalation events appear in the persisted trace; failed checks write
  a snapshot named by check id, successful checks write none.
- `tests/integration/test_check_traces.py`: SQLite round trip of a `CheckTrace`
  (events, kinds, details); missing trace → None; fresh DB is schema **v6**.

## Regression Statement

Savings detection, notifications, guided rebook, and the bolt 006 search journey are
unchanged consumers; all 277 pre-existing tests pass. `ExtractionMethod.AGENT` was
already permitted by the schema v5 CHECK constraint, so no further migration was
needed (v6 is purely additive `check_traces`).

## Not Covered (accepted)

- `AnthropicAgentBrain.decide` against the live SDK/network — the pure mapping
  (`action_from_tool_call`) is tested; the SDK call mirrors the bolt 003 extractor
  pattern and is validated in operations verification.
- `PlaywrightInteractiveBrowser.observe/act/screenshot` against a real browser —
  port-contract behavior is covered via the fake; live-site runs are the operations
  phase's manual verification, as for all Playwright code in this repo.
