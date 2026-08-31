---
stage: test
bolt: 061-agentic-inventory-executor
created: 2026-08-31T00:24:00Z
---

# Test Report: Reliable Browser Use Inventory Entry

## Summary

- **Focused tests**: 150 inventory executor/coordinator/account-sync tests and 70 Browser Use
  adapter tests passed during final construction.
- **Repository tests**: 1,880 passed with 55 existing deprecation warnings.
- **Static analysis**: Ruff passed; mypy passed across 128 source files.
- **AI-DLC integrity**: Artifact validator and status-integrity checks passed with zero issues
  after the completion amendment.
- **Authenticated VPS replay**: Three consecutive runs through one isolated coordinator using the
  production encrypted session each returned `observed`, one accepted positive, one eligible
  current-run booking, zero safety codes, one browser action, zero model cost, and 6.4-8.1-second
  latency. The daemon was stopped for the loop and restored healthy; Telegram was not required.

## Acceptance Criteria Validation

- ✅ Browser Use enters through the code-owned HTTPS `secure.booking.com/mytrips.html` route while
  the network guard continues to reject HTTP.
- ✅ Safe same-tab normalization, interactive-ancestor checks, prohibited-route checks, dialogs,
  downloads, extra targets, and mutation controls remain code-owned and fail closed.
- ✅ The exact Browser Use 0.11.13 structured-output mismatch is corrected by removing only disabled
  planning fields before Anthropic schema optimization; a regression exercises the exact optimizer.
- ✅ Positive submission and terminal schemas are reduced to bounded reliable claims; BookSaver
  supplies caller-owned identity/facts, derives incomplete scope evidence, and never authorizes
  absence from the model response.
- ✅ Caller-owned saved candidates are capped, unique, repr-redacted, session-bound, excluded from
  telemetry, and cannot resolve identity outside the caller's persisted set.
- ✅ Browser Use semantic text is retained only in six bounded in-memory episode snapshots. The
  common positive path resolves exact visible stay dates to exactly one caller-owned candidate;
  same-date ambiguity fails closed, unseen reservations remain preserved, and the LLM is skipped.
- ✅ Agentic positives reconcile a legacy internal reservation ID through unique caller-scoped
  confirmation identity, retain conflict checks, preserve established facts, and refresh the
  existing eligible projection instead of inserting a duplicate.
- ✅ Content-free diagnostics retain only closed action, field, validation, and guard categories;
  screenshots, URLs, page text, prompts, cookies, reasoning, and provider exceptions are not
  persisted.
- ✅ Stagehand and every non-`/bookings` inventory trigger remain unchanged; action, time, cost,
  egress, authentication, and teardown limits were not increased.

## Issues Found

- Browser Use 0.11.13's schema optimizer made disabled `current_plan_item` and `plan_update` fields
  required, causing valid model turns to fail before tool dispatch. The qualified output format now
  removes those fields only when planning is disabled.
- Production exposed that legacy inventory stores Booking's internal reservation ID while the
  semantic card can be matched through saved confirmation/property/date facts. Persistence now
  performs a caller-scoped confirmation lookup before agentic insert and retains established-fact
  conflict validation.
- The first repeated qualification loop accidentally mounted source at `/app/src` without adding
  that directory to Python's import path, so it re-exercised the prior immutable package. The
  corrected harness asserts the imported adapter path before every source-mounted replay.
- Browser Use vision could see and select the saved reservation while its serialized DOM omitted
  the full canonical property label. The common path now accepts only exact visible stay dates that
  resolve to one caller-owned saved reservation; the mature agent remains for navigation cases,
  and neither path can infer account completeness or absence.
- Iterative production qualification created one incomplete, unmonitored duplicate row before the
  confirmation merge existed. Operations must back up SQLite and remove only that exact test-created
  row before Telegram acceptance.

## Recommendations

- Build and replay the immutable final candidate image, then merge and deploy the exact merged image.
- Cursor Bugbot was unavailable due its service limit; the owner explicitly waived that review for
  this release. Retain the full local and production verification evidence in the construction and
  operations logs.
