---
id: 003-qualify-confirmation-total-for-affected-caller
unit: 013-confirmation-booked-total
intent: 023-replaceable-agentic-browser-executor
status: complete
priority: must
created: "2026-10-10T01:59:26Z"
assigned_bolt: 092-confirmation-booked-total
implemented: true
---

# US-228: Qualify the confirmation total for the affected caller

As a user, I want the corrected price verified against my real booking page before it is released.

## Acceptance criteria

- Deterministic tests cover the dollar layout, several other currencies, grouped thousands, mixed
  and unrecognized currencies, each refund-schedule rejection, tier precedence and both
  saved-total outcomes.
- When a confirmation is parsed but its total or refundability stays unknown, a content-free reason
  code is recorded so an unsupported layout can be identified without page content.
- An isolated replay of the affected caller's normal refresh, with notifications disabled and
  production state protected, shows the saved USD301 replaced by the confirmation total and the
  booking still eligible. Until then acceptance is not claimed.
- Run the full relevant test, Ruff, mypy and AI-DLC gates and record actual results and limitations
  in the test report before the completion cascade.
