---
id: 002-run-jev-as-the-price-method
unit: 004-jev-price-promotion
intent: 026-jev-price-comparison
status: complete
priority: must
created: "2026-10-10T01:45:00Z"
assigned_bolt: 089-jev-price-promotion
implemented: true
---

# US-217: Run Jev as the price method with the LLM path as rollback

## User story

As the owner, I want price checks to run on Jev only, so I stop paying for the LLM method, while
keeping that method available if Jev proves insufficient.

## Assigned requirement

FR-13.

## Acceptance criteria

- [ ] Given `agentic_browser.price_executor = "jev"` and a TypeSafe key, when a manual or
  scheduled check runs, then Jev's validated result is the canonical result: history, trace,
  failure counters, session refresh, canary metrics, savings rows and alerts.
- [ ] Given that mode, when a check runs, then no Anthropic price call is made and no comparison
  report is sent.
- [ ] Given that mode without a TypeSafe key, when starting, then price checks fail closed; the
  Anthropic key is never substituted (and vice versa).
- [ ] Given `price_executor = "jev"` together with `jev_comparison.enabled = true`, when loading
  config, then it is rejected.
- [ ] Given Jev as authority, when a run finishes, then its provider cost, certainty, latency and
  diagnostic are recorded durably and a daily cap is enforced before the next run; an unreadable
  ledger refuses the run.
- [ ] Given `price_executor = "browser_use"`, when restarting, then the previous LLM method runs
  unchanged (rollback), with history preserved.
- [ ] Given a user purge or booking removal, when deleting, then Jev run records are removed too.
- [ ] Given a reservation booked with meals and a rate whose name mentions a meal (for example
  "Flexible + Breakfast"), when Jev reports the rate's meal wording, then the rate's name is not
  part of it, so an explicit "breakfast included" line is classified as breakfast.

## Out of scope

Removing the LLM adapters; changing reservation discovery.
