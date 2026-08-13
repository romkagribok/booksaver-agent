---
unit: 002-dom-resilient-browser-workflows
bolt: 042-dom-resilient-browser-workflows
stage: test
status: complete
updated: 2026-08-13T03:29:32Z
---

# Test Report - DOM Registry and Protected-First Page Classification

## Outcome

BookSaver now declares every production DOM-sensitive Booking.com step in one closed registry and
classifies fresh page state with protected evidence before weak account chrome. Conclusive login,
MFA, captcha, bot-wall, destination, observation, provider, and budget outcomes stop under exact
typed reasons without a model call. Only unresolved page state invokes the caller-scoped adaptive
classifier.

## Verification Summary

| Gate | Result |
|---|---:|
| Resolver, classifier, runtime, and invalid-schema escalation set | 58 passed |
| Registry/classifier/auth/remote-auth focused set during integration | 136 passed |
| Final cross-browser resilience focused set | 258 passed |
| Full repository suite | 1512 passed |
| Ruff across `src` and `tests` | Passed |
| Strict mypy across `src` (117 files) | Passed |
| CLI help smoke | Passed |
| Diff whitespace validation | Passed |

The full suite emitted only the existing `schedule.check_interval` deprecation warnings.

## Acceptance Criteria Validation

- ✅ Nineteen production step definitions cover remote authentication, session validation,
  inventory, search/property/context/currency/rate, snapshot, and offer extraction seams.
- ✅ Workflow-owned `DOM_STEPS` declarations are structurally compared with the registry; missing,
  extra, or duplicate declarations fail with their workflow name.
- ✅ Legacy homepage form automation cannot satisfy production coverage.
- ✅ Changed login DOM retaining Genius/header/bookings chrome is not accepted as authentication.
- ✅ Credential, MFA, captcha, bot-wall, external, and mutating evidence outranks weak account
  chrome and executes no model-proposed action.
- ✅ A model-authenticated classification remains only a candidate; a fixed read-only probe and
  deterministic strong evidence are required before cookies can be saved or refreshed.
- ✅ The classifier accepts only typed state/confidence/evidence/operator-action output and never
  receives screenshots, URLs, selectors, hrefs, control values, cookies, or credential content.
- ✅ One invalid Sonnet schema is retried under the same session; two invalid schemas permit the
  sole Opus escalation, while low confidence may escalate directly and admission failures remain
  exact.

## Safety Boundary

Protected pages remain classification-only. The model cannot fill credentials, complete MFA,
bypass challenges, alter account or reservation state, or provide arbitrary actions, selectors,
scripts, or destinations.
