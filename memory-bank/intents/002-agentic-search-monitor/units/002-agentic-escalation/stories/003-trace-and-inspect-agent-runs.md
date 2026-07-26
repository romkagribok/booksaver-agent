---
id: 003-trace-and-inspect-agent-runs
status: complete
implemented: true
---

# US-022 Trace and inspect agent runs locally

**Intent:** `002-agentic-search-monitor`
**Unit:** `002-agentic-escalation`
**Status:** Ready
**Tag:** Phase 2

## Story

**As a** user
**I want** every check to leave an inspectable local trace of what the automation did
**So that** I can diagnose failed or suspicious checks without rerunning them blind

**Acceptance criteria**

- Given any completed check (success or failure)
- When it finishes
- Then an ordered step trace is persisted locally: scripted steps, escalations (trigger, observation
  tier, actions), LLM call counts, and final outcome
- And a CLI command (e.g. `booksaver checks trace <check-id>`) renders the trace
- Given a failed check
- When the failure occurs
- Then a page snapshot (page text; screenshot when one was already captured) is stored under the data
  directory, with rotation caps on count and total size
- And traces and snapshots redact cookies, credentials, and session tokens, and never leave the machine

---
