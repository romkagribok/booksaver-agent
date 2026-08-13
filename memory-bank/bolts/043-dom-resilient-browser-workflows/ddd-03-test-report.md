---
unit: 002-dom-resilient-browser-workflows
bolt: 043-dom-resilient-browser-workflows
stage: test
status: complete
updated: 2026-08-13T03:29:32Z
---

# Test Report - Guarded Adaptive Browser Workflows

## Outcome

Inventory synchronization, remote authentication, and customer-search price checks now use the
same registered, deterministic-first recovery boundary. Safe selector/control drift can be
recovered by Sonnet and, after measured quality failure, one Opus turn. Every registered terminal
path carries a canonical reason; grounded deterministic business exclusions remain exact and do
not spend a diagnosis call.

## Verification Summary

| Gate | Result |
|---|---:|
| BrowserAgent/domain focused set | 175 passed |
| Inventory/remote-auth focused set | 133 passed |
| Search/adaptive extraction focused set | 108 passed |
| Final cross-browser resilience focused set | 258 passed |
| Broader browser/monitor set during integration | 438 passed |
| Full repository suite | 1512 passed |
| Ruff across `src` and `tests` | Passed |
| Strict mypy across `src` (117 files) | Passed |
| Diff whitespace validation | Passed |

The full suite emitted only the existing `schedule.check_interval` deprecation warnings.

## Acceptance Criteria Validation

- ✅ Registered inventory steps pass exact `DomStepId` values; arbitrary strings fail before
  browser or provider I/O.
- ✅ Renamed safe controls can be interpreted under step capabilities and one relevant read-only
  Booking.com popup may be adopted only after code validates its destination and state.
- ✅ External, protected, mutating, multiple, additional, unsupported, and irrelevant popups are
  refused without transferring control.
- ✅ Reservation and offer facts remain advisory until independent code validates identity,
  completeness, equivalence, refundability, currency, and trusted inputs.
- ✅ Empty or invalid Sonnet inventory/offer extraction receives one eligible Opus attempt; final
  empty evidence becomes typed ambiguity or code maintenance rather than false absence.
- ✅ Non-empty grounded candidates rejected by deterministic domain rules remain exact business
  outcomes, including `no_equivalent_offer`, without an LLM explanation.
- ✅ Measured semantic no-progress and a rejected unsafe Sonnet proposal may request one Opus turn;
  proposed unsafe actions never execute.
- ✅ Opus recovery success records positive provenance; unverified Opus output returns a bounded
  typed ambiguity, unsupported-page, or code-maintenance diagnosis with no action authority.
- ✅ Remote-auth ambiguity is debounced, a model candidate can only trigger the fixed read-only
  inventory probe, and cookies require deterministic strong proof.
- ✅ Assisted diagnoses propagate through inventory/search results into the coordinator; exact
  auth/MFA/captcha/provider/budget stops retain their specific reason.

## Preserved Human Boundary

BookSaver never cancels, modifies, reserves, purchases, pays, or submits a final booking action.
Authentication, MFA, captcha, account settings, and transaction pages remain human-operated.
