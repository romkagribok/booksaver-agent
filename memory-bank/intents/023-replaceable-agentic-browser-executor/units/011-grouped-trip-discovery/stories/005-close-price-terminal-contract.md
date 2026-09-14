---
id: 005-close-price-terminal-contract
unit: 011-grouped-trip-discovery
intent: 023-replaceable-agentic-browser-executor
status: complete
priority: must
created: "2026-09-14T20:01:15Z"
assigned_bolt: 076-price-terminal-contract
implemented: true
---

# US-191: Close the price submission contract

As a user, I want an unavailable comparison to finish with a clear supported result rather than
spend the check repeatedly guessing how to stop.

## Acceptance criteria

- The model sees exactly the existing allowed non-observation statuses; invalid/success terminal
  submissions cannot bypass observation, safety or equivalence validation.
- Complete query facts and per-offer evidence have distinct instructions; incomplete query facts
  remain rejected while each visible offer retains its independently validated evidence flags.
- Interrupted episodes retain bounded content-free diagnostic evidence and propagate cancellation.
- Targeted contract/privacy tests and the repository quality gate pass. Caller replay establishes
  whether the observed timeout is resolved; no root-cause claim is made from the schema alone.
- Current-head Bugbot and replacement-image Dev/Staging remain mandatory before merge/promotion.
