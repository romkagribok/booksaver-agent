# ADR-016: Bounded action vocabulary via SDK tool-use, guarded at the adapter

- **Status**: accepted
- **Date**: 2026-07-06
- **Bolt**: 007-agentic-escalation (agentic-escalation)

## Context

The LLM must act on the page when scripted steps fail. The action interface determines
both robustness and the safety story: BookSaver's core product constraint is that no
automated path may cancel or purchase anything.

## Decision

1. The agent acts through a **closed vocabulary** exposed as Anthropic tool-use tools:
   `click(ref)`, `fill(ref, text)`, `select(ref, value)`, `scroll(direction)`,
   `extract(data)`, `request_screenshot()`, `give_up(reason)`. Element `ref`s come only
   from the current observation's enumeration — no raw CSS from the model, no
   `page.evaluate`, no arbitrary JS, no navigation to model-chosen URLs.
2. The loop is a **plain anthropic SDK tool-use loop** (one `messages.create` per
   turn) — no computer-use beta API, no agent frameworks (keeps ADR-003's dependency
   posture; runtime deps stay playwright + anthropic).
3. The **ActionGuard is enforced at the adapter boundary**, not in the prompt: click
   targets matching reservation-mutating labels/hrefs (reserve/book-now/checkout/
   payment/cancel) are refused before Playwright is called, and the post-action URL is
   re-checked. The prompt states the policy too, but safety never depends on it.

## Alternatives considered

- **Anthropic computer-use (screenshot + coordinates)**: strongest generality, but
  screenshot-per-turn cost (see ADR-015), beta surface, and coordinate clicking
  bypasses element-level guarding — the guard would have to infer what was clicked.
  Rejected for MVP of this intent.
- **Model emits CSS selectors / JS**: maximum flexibility, unbounded blast radius and
  unguardable targets. Rejected.
- **Agent framework (e.g. browser-use, LangChain)**: new runtime deps and opaque loops
  vs ~200 lines of owned code. Rejected per ADR-003.

## Consequences

- Safety is testable: guard tests enumerate blocked labels/hrefs/URLs; no prompt-
  injection on page content can produce a cancel/purchase action.
- The agent can only interact with what the enumeration surfaces; genuinely
  canvas-only widgets stay out of reach (accepted — give_up + coded failure beats an
  unguardable click).
- The same `AgentBrain` port isolates the SDK loop for future model/provider changes.
