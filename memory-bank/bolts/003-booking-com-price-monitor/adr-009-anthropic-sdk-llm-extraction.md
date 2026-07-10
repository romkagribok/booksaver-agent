---
unit: 002-booking-com-price-monitor
bolt: 003-booking-com-price-monitor
id: ADR-009
title: Anthropic SDK with a small default model for LLM extraction
status: accepted
updated: 2026-07-05T00:00:00Z
---

# ADR-009: Anthropic SDK for LLM extraction

## Context

US-006 requires LLM-assisted extraction when DOM selectors fail. Options: official
Anthropic SDK, OpenAI SDK, a provider-agnostic HTTP client, or a multi-provider
abstraction library (litellm etc.).

## Decision

Use the **official `anthropic` Python SDK**, defaulting to **`claude-haiku-4-5`**
(configurable via `[extraction] model` in config.toml). API key comes exclusively from
the `BOOKSAVER_LLM_API_KEY` environment variable (per ADR-002).

## Rationale

- Extraction is a narrow, well-scoped task (page text → JSON with price/currency/refund
  fields); a small fast model is sufficient and cheap per check.
- The official SDK handles retries, timeouts, and typed errors — less bespoke HTTP code
  to test, and failures map cleanly to `FailureReason(llm_error)` for US-014.
- A multi-provider abstraction adds a dependency layer we don't need for MVP; the
  `LLMExtractor` port already isolates the choice, so switching providers later means
  one new adapter, not a rewrite.

## Consequences

- MVP is Anthropic-only for extraction; other providers require a new adapter behind the
  same port (explicitly in scope for Unit 5 extensibility if wanted).
- Missing API key degrades gracefully to DOM-only mode with a startup log warning —
  the daemon never crashes for lack of a key (US-006 acceptance criteria).
- Model name is user-overridable in config to survive model deprecations without a release.
