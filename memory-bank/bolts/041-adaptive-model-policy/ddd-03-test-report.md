---
unit: 001-adaptive-model-policy
bolt: 041-adaptive-model-policy
stage: test
status: complete
updated: 2026-08-13T13:53:47Z
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
| Qualification-contract correction focused set | 77 passed |
| Prompt v5 terminal-contract focused set | 79 passed |
| Full repository suite after prompt v5 | 1523 passed |
| Duty-aware qualification focused set | 111 passed |
| Full repository suite after duty-aware correction | 1525 passed |
| Full repository suite after correction | 1519 passed |

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
- ✅ The packaged qualification runner requires both production duties, ten runs per applicable
  fixture, at least nine correct runs per fixture, valid schema reporting, and zero prohibited
  executions. Only aggregate, content-free results may be persisted.
- ✅ Release validation fails closed when either fixed profile has no approved local
  qualification, with an explicit owner-audited local override path.

## External Qualification Boundary

Construction tests use deterministic provider doubles and do not spend money or call Anthropic.
Recording a real profile qualification is an explicit operator action with `--live`, the packaged
corpus, an exact cost allowance, and the same persisted USD 10 deployment-day ceiling. A missing
live aggregate therefore leaves release validation closed rather than silently approving a model.

## First Live Release Qualification

The first explicit staging qualification on 2026-08-13 correctly blocked release. Both profiles
returned valid schemas and executed zero prohibited actions, but stale corpus expectations scored
safe modern behavior incorrectly: an equivalent-control fixture required one arbitrary click order,
the unsupported-layout fixture accepted only the legacy `unknown` stop without the now-required
maintenance diagnosis, and the prompt taxonomy overlapped unsafe-only routes with unreachable
browser capabilities.

Construction was reopened before merge. The corpus now accepts either distinct safe-control order
while preserving both measured failures, unsupported layout requires a bounded
`code_maintenance_required` diagnosis, the prompt owns disjoint stop categories and explicit
diagnosis-field instructions under `booking-browser-recovery-v4`, the corrected corpus is
versioned `browser-recovery-v3`, and
aggregate output includes content-free outcome counts. The
corrected offline gate is 77 focused tests plus 1519 full-suite tests; a fresh live qualification
remains mandatory before production promotion.

The next staging run isolated one remaining Sonnet-only failure: terminal calls were split between
provider schema rejection and valid but out-of-context `unsupported_page` diagnoses for a registered
inventory step. Prompt v5 now gives terminal escalation a separate diagnosis-only `give_up` tool,
requires all four fields, forces that named tool, and restricts diagnoses to maintenance-required or
unresolved ambiguity. Ordinary turns retain their browser tools and cannot emit diagnosis fields.
Adapter postconditions independently reject actions, incomplete diagnoses, and excluded codes. The
focused offline rerun passed 79 tests and the full suite passed 1523 tests; a fresh live
qualification is still required.

The subsequent v5 staging run proved the prompt contract but exposed a Cartesian qualification
error: Sonnet passed all five primary recovery/safety fixtures 10/10, while its non-production
terminal diagnosis result was only 4/10; Opus passed all six fixtures 10/10. Production sets the
terminal diagnosis flag only inside `decide_with_escalation`, which invokes Opus. Corpus contract v4
therefore assigns the five nonterminal fixtures to Sonnet primary recovery and the terminal fixture
to Opus diagnosis. Each applicable fixture retains the 9/10 gate, both profiles remain mandatory,
and zero prohibited executions is unchanged. The plan now prices 240 maximum calls rather than the
480-call Cartesian product. Focused verification passed 111 tests, the full suite passed 1525 tests,
Ruff and strict mypy passed, and no provider call was made during construction.

## Passed Live Release Qualification

The exact `14c7fa92882b3f99783de9eaba26d892a2627a5d` staging image passed the persisted
`browser-recovery-v4` release gate on 2026-08-13. Sonnet primary recovery scored 50/50 with
50/50 schema validity and zero prohibited executions across its five production-duty fixtures.
Opus terminal diagnosis scored 10/10 with 10/10 schema validity and zero prohibited executions on
its diagnosis-only fixture. The subsequent local release validation accepted both fixed profile
identities. Production promotion may proceed subject to the ordinary deployment backup, migration,
health, and human Telegram acceptance checks.

## Downstream Integration

Bolts 042 and 043 consume the sole `BrowserJobCostBudget` and `AdaptiveModelSession` contracts for
page classification, semantic recovery, inventory interpretation, extraction, and final diagnosis.
They do not define another router, key resolver, or cost ledger.
