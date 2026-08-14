---
unit: 002-dom-resilient-browser-workflows
bolt: 045-dom-resilient-browser-workflows
stage: test
status: complete
updated: 2026-08-14T02:24:00Z
---

# Test Report - Remote Authentication DOM Recovery

## Outcome

The `/connect` workflow now recognizes Booking.com's current mobile `/mytrips.html` inventory
shell without legacy test IDs. Unknown future layouts can reach the existing bounded classifier
instead of entering a fixed-probe reload loop. Sonnet output remains advisory: cookie capture
requires a fresh code-owned `StepVerificationResult` carrying a `CodeVerificationReceipt`, while
Opus remains diagnosis-only.

## Verification Summary

| Gate | Result |
|---|---:|
| Page-state, classifier, and remote-browser focused set | 90 passed |
| Remote-auth/coordinator/factory broader set | 167 passed |
| Full repository suite | 1539 passed |
| Ruff across `src` and `tests` | Passed |
| Strict mypy across `src` (117 files) | Passed |
| CLI help smoke | Passed |
| Diff whitespace validation | Passed |

The full suite emitted only the existing `schedule.check_interval` deprecation warnings.

## Acceptance Criteria Validation

- ✅ The production-shaped `Bookings & Trips` plus `Active`, `Past`, and `Canceled` mobile shell
  is deterministic inventory proof on an approved Booking.com inventory destination, with login,
  MFA, captcha, bot-wall, external, and prohibited evidence retaining precedence.
- ✅ A stable ambiguous page reaches Sonnet before the fixed probe; the probe is admitted once per
  remote-auth episode and redirects cannot reopen it into a reload loop.
- ✅ Classifier requests carry only bounded visible structure and opaque current element references;
  invented, stale, missing, or structurally insufficient references are quality failures.
- ✅ Grounded Sonnet inventory evidence is re-observed and checked for an unchanged fingerprint,
  an approved HTTPS Booking.com inventory destination, protected-state absence, and a heading plus
  an independent inventory companion role before code issues a receipt.
- ✅ Opus cannot issue a verification receipt or authorize cookie capture, even when its positive
  classification cites otherwise valid current references.
- ✅ Probe timeout and browser failures remain distinct observation/infrastructure outcomes instead
  of collapsing to a swallowed boolean.
- ✅ Persistent unverified semantic evidence ends with a canonical terminal diagnosis and existing
  post-cleanup incident handling rather than waiting silently for the ten-minute browser expiry.
- ✅ Transient page detachment is bounded; three consecutive loop failures end with an exact
  observation-unavailable or infrastructure diagnosis instead of being swallowed indefinitely.
- ✅ No model can enter credentials, solve human challenges, choose a destination, or perform a
  reservation/account mutation.

## Release Follow-up

This gate is code-complete but not deployed. Before production deployment, run the repository's
live model qualification for the changed page-classification prompt and then perform human Telegram
acceptance with `/connect`, `/status`, `/bookings`, and `/checknow` as applicable.
