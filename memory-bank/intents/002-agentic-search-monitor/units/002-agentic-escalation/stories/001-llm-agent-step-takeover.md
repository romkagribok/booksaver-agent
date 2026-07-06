---
id: US-020
status: complete
implemented: true
---

# US-020 LLM browser agent takes over failed journey steps

**Intent:** `002-agentic-search-monitor`
**Unit:** `002-agentic-escalation`
**Status:** Ready
**Tag:** Phase 2

## Story

**As a** user
**I want** an LLM agent to complete a journey step when the scripted automation gets stuck
**So that** checks keep working when Booking.com changes its UI, without me babysitting selectors

**Acceptance criteria**

- Given a journey step that fails (missing selector, unexpected page, popup/overlay, ambiguous room table)
- When escalation triggers
- Then an LLM agent loop receives the step goal and a **tiered observation**: first a distilled
  text/DOM snapshot (visible text + interactive elements with stable references); a screenshot is
  attached only when the agent signals it cannot orient from text or two consecutive actions fail
- And the agent acts only through a bounded vocabulary — click, fill, select, scroll, extract,
  give-up — executed via the existing browser port (no arbitrary JS)
- And on step success control returns to the scripted journey at the next step
- And on give-up the check fails with `AGENT_GAVE_UP` including the step name and the agent's stated
  reason
- And every escalation is logged with step name, trigger reason, observation tier used, and actions taken
- And the check history records whether a successful check was scripted-only or agent-assisted

---
