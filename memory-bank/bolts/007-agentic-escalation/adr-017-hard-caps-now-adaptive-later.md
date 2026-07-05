# ADR-017: Hard per-check cost caps now; adaptive budgeting is named future work

- **Status**: accepted
- **Date**: 2026-07-06
- **Bolt**: 007-agentic-escalation (agentic-escalation)

## Context

An LLM-driven loop inside an unattended daemon is a runaway-cost risk: a stuck page
could burn tokens every scheduled tick. The intent requires the daemon's cost per check
to be bounded and diagnosable.

## Decision

Three **hard, config-driven caps** per booking check, in `config.toml` `[agent]`
(user decision at intent-002 Checkpoint 1):

| Cap | Default | Notes |
|-----|---------|-------|
| `max_steps` | 15 | agent turns per check; screenshot (tier-2) turns count double (ADR-015) |
| `max_llm_calls` | 20 | every LLM call in the check — agent turns **and** bolt 006's `extract_offers` draw from one pool |
| `check_timeout_seconds` | 180 | wall-clock per booking check, checked between steps/turns |

First breach aborts the check with the distinct `BUDGET_EXCEEDED` failure code; the
daemon proceeds to the next booking/cycle normally.

**Documented limitation (user request)**: hard caps are the deliberately simple first
version of cost control. If they prove too blunt in practice (checks failing on cap
while making progress), the named future work is *adaptive budgeting* — e.g. per-day
token budgets across checks, backoff when a booking repeatedly needs escalation,
cheaper-model downshift for easy turns. This note also lives in the README so it
survives outside the memory bank.

## Alternatives considered

- **Soft limits (warn only)** and **no limits**: rejected by user — unbounded worst-case
  spend in an unattended daemon.
- **Token-denominated budget**: more precise than step counts but harder to reason
  about in config and requires SDK usage accounting up front; deferred to the adaptive
  future work.

## Consequences

- Worst-case cost per check is calculable from config; a wedged page costs at most one
  cap's worth per tick.
- Some genuinely-hard checks will fail on cap; `BUDGET_EXCEEDED` in check history plus
  the trace (US-022) make those visible and tunable.
- The single LLM-call pool means heavy escalation can consume the extraction budget —
  acceptable: the check would fail either way, and the trace shows where it went.
