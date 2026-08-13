---
id: 004-explain-every-terminal-browser-outcome
unit: 002-dom-resilient-browser-workflows
intent: 022-adaptive-booking-browser-resilience
status: complete
priority: must
created: 2026-08-13T01:59:59.000Z
assigned_bolt: 043-dom-resilient-browser-workflows
implemented: true
---

# Story: Explain Every Terminal Browser Outcome

## User Story

**As a** BookSaver user and operator
**I want** every failed browser job to say what stopped it and what to do
**So that** authentication, DOM drift, model quality, cost, and infrastructure problems are not
collapsed into the same generic failure

## Acceptance Criteria

- [ ] **Given** a registered DOM step remains ambiguous after safe Sonnet recovery, **When** provider
  and reserved budgets permit, **Then** Opus receives one diagnosis-only turn and returns a
  validated category, confidence, safe evidence class, maintenance flag, and operator action.
- [ ] **Given** deterministic evidence already proves reauthentication, MFA, captcha/bot wall,
  destination block, observation failure, provider failure, or budget/time limit, **When** the job
  terminates, **Then** it preserves that reason and guidance with zero diagnosis-only model calls.
- [ ] **Given** model `authentication_required`, captcha, unavailable, or no-progress output occurs,
  **When** workflow/coordinator mappings run, **Then** the matching domain failure survives without
  becoming generic `gave_up`, `navigation_failed`, `currency_mismatch`, or `extraction_failed`.
- [ ] **Given** observation, provider, key, pricing, time, job-cost, daily-cost, or infrastructure
  failure prevents an LLM diagnosis, **When** the job ends, **Then** that exact system reason and
  provenance are recorded without pretending the LLM diagnosed DOM drift.
- [ ] **Given** a registered DOM-sensitive path has a current observation, **When** all mappings are
  tested, **Then** it cannot terminate as generic `unknown`, `navigation_failed`, or
  `extraction_failed`.
- [ ] **Given** a caller receives failure text, **When** the reason is auth, retryable provider/cost,
  or maintenance drift, **Then** Telegram supplies safe `/connect`, retry/wait, or preserved-data
  guidance while the owner audit receives named step and incident input.
- [ ] **Given** any terminal result, **When** cleanup completes, **Then** pages, contexts, coordinator
  gate, and reservations/opportunities remain in the correct safe state.

## Technical Notes

- Normalize terminal reason before inventory/search/currency/extraction-specific result mapping.
- Preserve source provenance: deterministic policy, Sonnet, Opus, provider admission, or infrastructure.
- This story directly fixes current `authentication_required` → `gave_up` propagation.

## Dependencies

### Requires

- US-130 through US-135.

### Enables

- Unit 3 incident correlation and accurate user guidance.

## Edge Cases

| Scenario | Expected Behavior |
|----------|-------------------|
| Opus says maintenance but code sees protected page | Protected state wins; diagnosis audit notes disagreement safely |
| LLM provider times out after actions | Provider timeout reason plus verified page state; no generic failure |
| Catch-all exception has sensitive text | Map exception class/category only; do not expose message |
| Failure occurs after positive partial inventory | Preserve validated positives and last conclusive unseen records |

## Out of Scope

- Repeating a known deterministic explanation through an LLM.
- Guaranteeing an LLM explanation when the page cannot be observed or Anthropic cannot be called.
- Allowing a diagnosis to override deterministic safety or domain state.
