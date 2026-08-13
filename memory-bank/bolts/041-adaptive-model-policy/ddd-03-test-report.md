---
unit: 001-adaptive-model-policy
bolt: 041-adaptive-model-policy
stage: test
status: complete
updated: 2026-08-13T03:00:30Z
---

# Test Report - Adaptive Model Policy

## Outcome

BookSaver now has a fixed Sonnet 5 primary and Opus 5 escalation portfolio with no Fable or
arbitrary-model path. Predictable terminal states can stop without creating a model session,
while ambiguous episodes reserve every physical call against the same caller-scoped browser-job
budget before provider access. Exact usage is reconciled into a restart-safe deployment UTC-day
ledger.

## Verification Summary

| Gate | Result |
|---|---:|
| Policy, persistence, runtime, qualification, replay, config, and CLI focused set | 76 passed |
| Full repository suite at completion of the policy implementation | 1253 passed |
| Ruff across `src` and `tests` at completion of the policy implementation | Passed |
| Strict mypy across `src` at completion of the policy implementation | Passed |
| Diff whitespace validation | Passed |

The focused rerun completed on 2026-08-13 after the qualification aggregate and truthful
`completed` provider outcome were added. Expected legacy `schedule.check_interval` deprecation
warnings were emitted; no test failed.

## Acceptance Criteria Validation

- ✅ Only measured schema, confidence, semantic-progress, and safety-quality failures can request
  the single Opus escalation.
- ✅ Authentication, MFA, CAPTCHA, provider, budget, time, and other exact stops do not trigger an
  ineffective quality escalation.
- ✅ Conservative admission happens before every physical call and enforces USD 1 per browser job
  and USD 10 per deployment UTC day using exact integer microdollars.
- ✅ Sonnet 5 uses the published introductory price through 2026-08-31 UTC and automatically adopts
  the published standard price on 2026-09-01, preventing future under-reservation.
- ✅ One immutable caller key reference is shared by Sonnet and Opus; job-global attempt ordering
  spans recovery, interpretation, extraction, classification, and diagnosis.
- ✅ Fable and arbitrary profiles are rejected by domain and configuration validation.
- ✅ The packaged qualification runner requires both profiles, ten runs per fixture, at least
  nine correct runs per fixture, valid schemas, and zero prohibited executions. Only aggregate,
  content-free results may be persisted.
- ✅ Release validation fails closed when either fixed profile has no approved local
  qualification, with an explicit owner-audited local override path.

## External Qualification Boundary

Construction tests use deterministic provider doubles and do not spend money or call Anthropic.
Recording a real profile qualification is an explicit operator action with `--live`, the packaged
corpus, an exact cost allowance, and the same persisted USD 10 deployment-day ceiling. A missing
live aggregate therefore leaves release validation closed rather than silently approving a model.

## Downstream Integration

Bolts 042 and 043 consume the sole `BrowserJobCostBudget` and `AdaptiveModelSession` contracts for
page classification, semantic recovery, inventory interpretation, extraction, and final diagnosis.
They do not define another router, key resolver, or cost ledger.
