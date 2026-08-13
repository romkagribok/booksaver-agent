---
unit: 003-dom-drift-incident-operations
bolt: 044-dom-drift-incident-operations
stage: test
status: complete
updated: 2026-08-13T03:29:32Z
---

# Test Report - DOM Drift Incident Operations

## Outcome

Eligible assisted DOM outcomes are now correlated into restart-safe, content-free maintenance
incidents. The owner is alerted immediately for a code-maintenance diagnosis or after the second
matching fingerprint within six hours. Sanitized diagnostics are encrypted locally, inspectable
only from the local CLI, and expire after exactly seven days.

## Verification Summary

| Gate | Result |
|---|---:|
| Incident persistence, migration, scoping, and encryption set | 91 passed |
| Incident application/CLI/Telegram integration set | 83 passed |
| Final migration/privacy/operator focused set | 201 passed |
| Full repository suite | 1512 passed |
| Ruff across `src` and `tests` | Passed |
| Strict mypy across `src` (117 files) | Passed |
| CLI help exposes `incidents` and `evaluate` | Passed |
| Diff whitespace validation | Passed |

The full suite emitted only the existing `schedule.check_interval` deprecation warnings.

## Acceptance Criteria Validation

- ✅ Predictable auth/MFA/captcha/provider/budget/infrastructure outcomes create no DOM incident.
- ✅ Sonnet/Opus-assisted recovery and typed model diagnoses produce content-free fingerprints;
  code-maintenance diagnoses alert immediately and other matches alert on occurrence two in six
  hours.
- ✅ Later deterministic success resolves matching observing/open incidents; assisted success does
  not prematurely resolve them.
- ✅ Schema v15 is additive from v13 or v14 and preserves spend, qualification, user, and booking
  data.
- ✅ Correlation, alert claiming, retry state, stale-claim recovery, and resolution are
  transactional and concurrency-tested.
- ✅ Telegram notices contain only incident ID, registered journey/step, typed category, occurrence,
  model roles, provider/budget state, evidence state, and the local inspection command.
- ✅ Invited users cannot see owner incident counts or trigger diagnostic provider work.
- ✅ Evidence contains only allowlisted structural role codes, closed action outcomes, and
  identifier-free ordered model-attempt metadata; labels, refs, page text, URLs, selectors,
  screenshots, prompts/responses, raw errors, and ledger IDs do not cross the boundary.
- ✅ Incident persistence happens after browser cleanup and is isolated from the completed caller
  result.
- ✅ Ciphertext expires at the exact seven-day boundary and user purge removes matching or
  undecryptable diagnostic evidence before deleting the user.

## Optional Image Boundary

No diagnostic screenshot is persisted. The design explicitly permits omission when safe visual
redaction cannot be proven; BookSaver never stores an unsanitized fallback.
