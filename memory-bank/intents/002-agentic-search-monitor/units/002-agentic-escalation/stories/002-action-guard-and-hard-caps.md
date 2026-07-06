---
id: US-021
status: complete
implemented: true
---

# US-021 Enforce action guard and hard cost caps

**Intent:** `002-agentic-search-monitor`
**Unit:** `002-agentic-escalation`
**Status:** Ready
**Tag:** Phase 2

## Story

**As a** user
**I want** the browser agent to be provably read-only on my account and bounded in cost
**So that** an automated check can never cancel/book anything or run up an unbounded LLM bill

**Acceptance criteria**

- Given any agent (or scripted) action during a check
- When it would navigate into or submit toward a reservation-mutating flow (cancellation pages,
  checkout/"reserve"/"book now" submission, payment)
- Then the action is blocked at the adapter level (URL/action denylist), recorded as `BLOCKED_ACTION`,
  and the agent must choose another action or give up
- Given `config.toml` `[agent]` settings
- When config loads
- Then max agent steps (default 15), max LLM calls per check (default 20), and per-check wall-clock
  timeout (default 180s) are validated (positive, sane bounds) with clear errors
- And screenshot-tier agent turns count double against the step cap
- When any cap is exceeded mid-check
- Then the check aborts with `BUDGET_EXCEEDED` (distinct in history and logs) and the daemon proceeds
  to the next booking/cycle normally
- And user docs note the caps are the deliberately simple first version — smarter adaptive budgeting
  is future work if hard caps prove too blunt

---
