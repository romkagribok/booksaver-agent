---
stage: test
bolt: 058-agentic-inventory-executor
created: 2026-08-28T01:44:57Z
---

# Test Report: Provider-Compatible Agentic Inventory Schemas

## Summary

- **Focused regression**: 57 agentic inventory adapter tests passed; 163 focused executor,
  coordinator, persistence, and model-policy tests passed during construction.
- **Full repository**: 1793 passed with 55 existing deprecation warnings.
- **Static checks**: Ruff clean; mypy clean across 127 source files.
- **AI-DLC checks**: artifact validation and status integrity both report zero issues across 58
  bolts and 23 intents.
- **Provider smoke**: the exact candidate Docker image completed a cookie-free Stagehand extraction
  through Anthropic and returned a typed `unavailable` terminal with 2806 input and 217 output
  tokens; the guarded computer-use tools also passed a direct Anthropic schema-admission smoke.
- **Diff hygiene**: `git diff --check` clean.

## Acceptance Criteria Validation

- ✅ **US-158 / Stagehand schema**: semantic extraction uses required string fields and explicit
  `unknown` sentinels, producing zero provider-compiled union parameters while Pydantic retains the
  typed response shape.
- ✅ **US-158 / Anthropic tools**: unsupported strict-schema constraints are removed; the large
  observation tool relies on typed decoding and code-owned bounds, while the small terminal tool
  remains strict.
- ✅ **US-158 / fail closed**: unknown completeness maps only to `incomplete`; invalid identities,
  dates, amounts, occupancy, enum values, and oversized values are rejected or omitted before the
  trusted validation boundary.
- ✅ **US-158 / diagnostics**: provider failures log only execution, phase, bounded category, and
  exception type; raw provider messages and page content are not persisted.
- ✅ **US-158 / unchanged authority**: navigation guards, session leases, positive-only
  reconciliation, action/deadline/cost caps, and BookSaver validation remain unchanged.

## Issues Found

- The first candidate smoke exposed Anthropic's broader strict-grammar complexity limit after the
  documented union and keyword failures. The large observation tool was made non-strict while
  retaining typed decoding and code-owned bounds; the small terminal tool remains strict.
- After the provider schema compiled, the signed-out smoke returned `unknown` completeness. That
  value now normalizes only to fail-closed `incomplete` evidence rather than aborting the episode.

## Remaining Release Gates

- Cursor Bugbot must pass on the final pushed head before merge.
- The exact merged Docker image must pass rollback capture, service health, database, Telegram,
  provider, and runtime verification before the release is considered operationally proven.
