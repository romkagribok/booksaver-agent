---
id: 003-qualify-grouped-discovery-and-final-image
unit: 011-grouped-trip-discovery
intent: 023-replaceable-agentic-browser-executor
status: complete
priority: must
created: "2026-09-13T16:10:04Z"
assigned_bolt: 074-grouped-trip-discovery
implemented: true
---

# US-189: Qualify grouped discovery for the actual caller and final image

As the owner, I want fixtures and real caller evidence proving grouped-trip coverage so a passing
simple-account replay or partial record count cannot be mistaken for a complete fix.

## Acceptance Criteria

These criteria govern construction acceptance; the mandatory Operations/release exit criteria
below remain required before release completion.

- Deterministic fixtures cover multiple trip groups/reservations, detail traversal, continuation
  after accepted positives, first-time versus saved-match lifecycle parity through persistence,
  display and eligibility, partial-saved retry requiring detail collection with the eligible-owner
  shortcut preserved, missing/conflicting facts, current/upcoming separation, and coverage
  failure under authentication/safety/deadline/action/cost constraints.
- The actual father's account is replayed through the normal caller-bound coordinator using
  isolated state, current consent/routing/session checks, notification suppression, and serialized
  browser admission. No production booking/session truth is mutated for a probe.
- Compare expected reachable groups/reservations/details against code-owned observed coverage and
  report each acceptance/rejection/missing-detail outcome. Explain legitimately ineligible rows;
  zero eligibility cannot be silently treated as successful price qualification.
- Verify/repair/replay until the agreed actual-caller coverage and fact criteria pass, or preserve
  precise external blocking evidence; do not replace them with owner, empty-account, or fixture
  success. Actual price results remain distinct from inventory acceptance.
- Run the repository quality gate for the final construction candidate and document the mandatory
  release checklist below, including remaining evidence and protected rollback arrangements.

## Mandatory Operations / Release Exit Criteria

- Obtain successful final-head Cursor Bugbot review and pass the merge gate before merging. Build and
  stage the final reviewed source; promotion must use the exact verified image or explicitly
  qualify any replacement image before release.
- After deployment, verify image/revision, process, logs, health, dependencies, and ports, then
  report deployed caller acceptance separately from native user Telegram interaction and price
  results. Retain protected backups/rollback and restore the daemon after any probe pause.

## Phase Clarification

On September 14, the acceptance wording was clarified to follow the existing Bolt 073 separation
between construction and Operations. Actual-caller verification, the final quality gate, and a
documented release checklist are construction requirements. Bugbot, final-image qualification,
promotion, and post-deployment verification are mandatory release exit criteria. This removes the
circular requirement to deploy before construction can hand off to Operations; it waives no gate,
records no completion, and changes no artifact status.

## Dependencies

US-187 and US-188, existing operator replay, and operations procedures. The user's end-to-end
approval covers this workflow; final-head review and safety boundaries remain mandatory.

## Final construction evidence

The father's September13 reconnect remained valid for September14 caller replay 22. The normal
invited-user coordinator on cloned state covered two groups with zero unresolved items, persisted
six observations and qualified two future stays. The following normal immediate check returned
a validated EUR price with authenticated-mobile provenance, no fallback or safety violations.
The source gate passed 2,564 tests with 83% measured coverage, Ruff/mypy and 16 validator tests.
See Bolt 074's final test report for exact coverage, timing, legitimate ineligibility and limitations.
The mandatory Operations/release criteria above remain pending; no deployment is inferred.
