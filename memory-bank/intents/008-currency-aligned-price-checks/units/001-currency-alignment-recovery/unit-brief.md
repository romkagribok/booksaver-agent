---
unit: 001-currency-alignment-recovery
intent: 008-currency-aligned-price-checks
phase: inception
status: ready
unit_type: cli
default_bolt_type: simple-construction-bolt
created: 2026-07-19T00:32:13Z
updated: 2026-07-19T00:32:13Z
---

# Unit Brief: Currency Alignment Recovery

## Purpose

Keep Booking.com price checks comparable when VPS localization renders an otherwise-valid refundable
offer in a currency different from the registered baseline, without weakening BookSaver's strict
same-currency savings invariant.

## Scope

### In Scope

- Propagate baseline currency through trusted search and property URLs.
- Identify candidates rejected only for currency after all prior eligibility checks pass.
- Retry currency alignment once with deterministic preference first and guarded-agent fallback.
- Re-extract offers under the existing cost and wall-clock budgets.
- Return and expose a currency-specific terminal failure when alignment cannot be verified.
- Exercise both scheduled and Telegram `/checknow` paths through their shared coordinator.

### Out of Scope

- FX conversion, exchange-rate providers, automatic baseline mutation, or informational conversion.
- Relaxed property, date, occupancy, room, refundability, or all-in-total matching.
- Additional browser concurrency, a new daemon process, database migration, or runtime dependency.
- Live Booking.com CI tests that would be flaky or trigger anti-automation controls.

## Assigned Requirements

| FR | Requirement | Priority |
|----|-------------|----------|
| FR-1 | Carry baseline currency as trusted search context | Must |
| FR-2 | Verify rendered offer currency | Must |
| FR-3 | Perform one bounded currency-alignment recovery | Must |
| FR-4 | Fail closed with actionable currency diagnostics | Must |
| FR-5 | Preserve all existing check entry points and safety gates | Must |

## Domain Concepts

### Key Concepts

| Concept | Description | Relevant attributes |
|---------|-------------|---------------------|
| Baseline currency | Canonical currency recorded with the original booking total | ISO-4217 code |
| Observed offer currency | Currency parsed from rendered room/rate evidence | ISO-4217 code, amount |
| Currency-only exclusion | Candidate that passed refundability, room, and confidence but differs in currency | candidate, baseline currency |
| Alignment recovery | Single bounded attempt to change Booking.com's display preference and re-extract | method, attempt count, outcome |
| Currency alignment failure | Terminal fail-closed check result after recovery is unavailable or ineffective | desired/observed currencies, detail |

### Key Operations

| Operation | Description | Inputs | Outputs |
|-----------|-------------|--------|---------|
| Build trusted URL | Adds authoritative currency alongside dates and occupancy | booking, result href | safe Booking.com URL |
| Classify selection | Separates currency-only eligible candidates from other exclusions | candidates, booking | chosen offer or evidence |
| Align currency | Applies same-site preference deterministically or through guarded fallback | booking, browser, budgets | recovery outcome |
| Re-extract once | Parses refreshed room/rate evidence without resetting budgets | page text, booking | candidate selection |
| Format terminal result | Exposes mismatch evidence safely in traces and Telegram | check failure | actionable message |

## Story Summary

| Metric | Count |
|--------|-------|
| Total Stories | 5 |
| Must Have | 5 |
| Should Have | 0 |
| Could Have | 0 |

### Stories

| Story ID | Title | Priority | Status |
|----------|-------|----------|--------|
| US-057 | Propagate baseline currency through trusted navigation | Must | Draft |
| US-058 | Verify rendered candidate currencies | Must | Draft |
| US-059 | Recover an otherwise-valid mismatch once | Must | Draft |
| US-060 | Report unresolved currency alignment safely | Must | Draft |
| US-061 | Preserve the shared check pipeline and safety gates | Must | Draft |

## Dependencies

### Depends On

| Capability | Reason |
|------------|--------|
| Intent 002 / bolt 006 | Trusted search/property context, candidate extraction, and offer selection |
| Intent 002 / bolt 007 | Guarded browser agent, cost caps, action guard, and trace recording |
| Intent 003 / Telegram gateway | User-facing check-result transport |
| Intent 007 / CheckCoordinator | Shared scheduled/on-demand execution and budgets |

### Depended By

| Consumer | Reason |
|----------|--------|
| Savings pipeline | Receives only a verified same-currency live price |
| VPS operations | Needs currency-localization failures to recover or be diagnosable |

### External Dependencies

| System | Purpose | Risk |
|--------|---------|------|
| Booking.com | Currency preference and rendered room/rate evidence | High |
| Anthropic API | Optional guarded visible-selector recovery | Medium |
| Telegram Bot API | On-demand completion result | Low |

## Technical Context

Use existing Python 3.11+, synchronous Playwright abstraction, plain Anthropic tool-use agent,
`Money`, `Booking`, `OfferSelection`, `CheckResult`, trace recorder, and Telegram formatting. Add no
dependency or persistence schema. Keep URL preference construction isolated and verified by tests.

## Constraints

- Same-currency arithmetic remains the final savings gate even after upstream alignment.
- Candidate currency evidence must be rendered/extracted; requested preference alone is insufficient.
- One recovery attempt per check, with no budget or timeout reset.
- LLM actions remain allowlisted and destructive navigation remains blocked.
- Currency mismatch must not be reported as ordinary room/refundability absence after recovery.

## Success Criteria

### Functional

- [ ] Search and property navigation request the baseline currency as trusted context.
- [ ] Currency-only eligible candidates are distinguishable from other exclusions.
- [ ] One deterministic/agent-assisted recovery can yield a verified same-currency success.
- [ ] Persistent mismatch produces a currency-specific, actionable result without savings.
- [ ] Scheduled and on-demand paths share the behavior.

### Non-Functional

- [ ] No cross-currency comparison, recursive retry, new dependency, or schema migration.
- [ ] Existing quotas, timeout, LLM budgets, action guards, and rebook confirmation remain intact.
- [ ] Full pytest, Ruff, and mypy gates pass.

### Quality

- [ ] All acceptance criteria have automated coverage where practical.
- [ ] Memory-bank artifacts and story index remain consistent.
- [ ] Human review occurs before commit and push.

## Bolt Suggestion

| Bolt | Type | Stories | Objective |
|------|------|---------|-----------|
| `020-currency-alignment-recovery` | Simple Construction | US-057–US-061 | Deliver the cohesive currency-alignment correction and regression proof |

## Notes

The feature deliberately prefers deterministic same-site preference setting; the LLM is the adaptive
fallback for visible control drift, while code verification remains authoritative.
