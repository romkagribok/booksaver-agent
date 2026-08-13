---
unit: 002-dom-resilient-browser-workflows
bolt: 043-dom-resilient-browser-workflows
stage: test
status: complete
updated: 2026-08-13T13:34:43Z
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
| Full repository suite | 1519 passed |
| Ruff across `src` and `tests` | Passed |
| Strict mypy across `src` (117 files) | Passed |
| Diff whitespace validation | Passed |
| Prompt v5 terminal-contract focused set | 79 passed |
| Full repository suite after prompt v5 | 1523 passed |

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
- ✅ Opus recovery success records positive provenance; an unverified registered-step Opus turn
  has only diagnosis authority and returns bounded ambiguity or code-maintenance.
- ✅ Remote-auth ambiguity is debounced, a model candidate can only trigger the fixed read-only
  inventory probe, and cookies require deterministic strong proof.
- ✅ Assisted diagnoses propagate through inventory/search results into the coordinator; exact
  auth/MFA/captcha/provider/budget stops retain their specific reason.
- ✅ Recovery prompt v5 distinguishes unsafe-only visible routes, confirmed-but-unreachable
  controls, and unsupported DOM. Its terminal contract forces actionless `give_up`, requires all
  diagnosis fields, and excludes `unsupported_page` after registered-step admission; changed or
  absent registered structure requests the maintenance diagnosis that drives owner notification.

## Preserved Human Boundary

BookSaver never cancels, modifies, reserves, purchases, pays, or submits a final booking action.
Authentication, MFA, captcha, account settings, and transaction pages remain human-operated.
