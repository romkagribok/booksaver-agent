# ADR-015: Tiered agent observations — text/DOM first, screenshot on demand

- **Status**: accepted
- **Date**: 2026-07-06
- **Bolt**: 007-agentic-escalation (agentic-escalation)

## Context

The escalated browser agent must "see" the page to choose actions. Vision (screenshots)
is the most robust observation but is the most expensive per turn (image tokens, larger
model requirement) and is usually unnecessary: Booking.com pages carry rich text and
accessible element labels.

## Decision

Observations are **tiered** (user decision at intent-002 Checkpoint 2/3):

1. **Tier 1 (default)**: distilled text observation — URL, title, bounded visible text
   (≤ 30k chars), and an enumerated list of visible interactive elements
   (`e0..eN`: role, label, href) that doubles as the action target namespace.
2. **Tier 2 (escalated)**: a viewport screenshot is attached only when the agent
   explicitly calls `request_screenshot`, or automatically after **two consecutive
   failed actions**.
3. **Screenshot turns cost double** against the step budget, keeping vision a
   deliberate spend, not a habit.

## Alternatives considered

- **Screenshot-every-turn (computer-use style)**: most robust, but multiplies cost per
  check for a daemon that runs on a schedule forever; rejected as the default.
- **Text-only, no vision at all**: cheapest, but leaves the agent blind to canvas/image
  widgets (some date pickers, captcha layouts) with no fallback; rejected.

## Consequences

- Happy-escalation cost stays near tier-1 token prices; vision remains available for
  exactly the pages that need it.
- The element enumeration in the adapter becomes the action contract (`click(ref)`),
  which also keeps the agent off arbitrary selectors/JS.
- Budget accounting must know the tier of each turn (implemented in `AgentBudget`).
