---
unit: 002-dom-resilient-browser-workflows
bolt: 043-dom-resilient-browser-workflows
stage: design
status: complete
updated: 2026-08-13T02:39:01Z
---

# Technical Design - Semantic DOM Recovery and Terminal Diagnosis

## Shared Runtime

```text
deterministic verifier
  |-- verified ------------> success, zero model calls
  |-- exact known failure --> exact typed result, zero explanation calls
  `-- ambiguous
       |-- Sonnet action or typed positive facts
       |-- ActionGuard + step capability + fresh code verifier
       |     `-- verified --> recovered
       `-- unresolved eligible quality failure
             `-- Opus diagnosis-only --> TerminalBrowserDiagnosis
```

The runtime reuses `AdaptiveModelSession`, `BrowserJobCostBudget`, the Bolt 042 step registry, and
page-state resolver. It adds no routing, budget, model, pricing, or caller-key types.

## Layer Changes

### Domain and Application

- Extend browser resilience types with semantic fact/evidence, three-state verification, popup
  result, and canonical terminal diagnosis.
- Preserve diagnosis through `EscalationResult`, `JourneyResult`, `CheckResult`,
  `InventoryDiscoveryResult`, and synchronization report mappings.
- Add strict semantic interpreter and diagnosis-only ports. Invalid tool/schema response is a
  quality outcome; actual provider/auth/rate-limit/outage remains a terminal provider outcome.

### Browser Agent

- Enforce the registered step capability before ActionGuard. Href controls remain limited to
  allowlisted read-only Booking.com routes. No-href clicks are allowed only for explicitly declared
  scope/pagination capabilities.
- Accept a positive semantic observation only when every fact is supported by current visible
  evidence and its value is compared by a code verifier.
- Do not re-run a missing legacy selector as the sole postcondition when semantic verification has
  proved the intended state.
- Preserve exact stop types. `authentication_required`, captcha, provider, budget, observation, and
  policy stops never become `gave_up`.

### Search Journey and Extraction

- Missing property-card selectors remain ambiguous; only grounded explicit absence produces
  `PROPERTY_NOT_FOUND`/unavailable.
- Opening a property verifies requested property identity, not merely any `/hotel/` URL.
- Context verification can consume grounded visible dates/occupancy; explicit trusted mismatch is
  deterministic.
- Empty/invalid DOM or model offer extraction stays ambiguous and receives bounded recovery/
  diagnosis. Grounded model offers enter existing refundability/equivalence/currency selection;
  ungrounded fields are discarded.
- Currency control drift may recover, while persistent rendered currency mismatch remains exact.

### Account Inventory

- Readiness, scope, pagination, detail, and extraction consume registered step capabilities and
  semantic facts. Renamed safe controls can be used without weakening global negative/mutating
  guards.
- Model facts may enrich visible positive reservation evidence but cannot prove an empty account,
  absent reservation, traversal completeness, or lifecycle change.
- Authentication/captcha/provider/budget/observation results map exactly through synchronization.

### Popup Adoption

Add one infrastructure-owned browser operation that can adopt exactly one newly opened child page.
Before control transfer, verify:

- HTTPS Booking.com origin;
- exactly one popup since the guarded action;
- `/hotel/...` for property navigation or approved reservation-detail route for inventory;
- no protected, external, checkout, payment, cancel, modify, account-setting, or other mutating path.

After adoption, capture fresh evidence and run the ordinary verifier. Any unknown/additional/
irrelevant/protected popup returns an exact refusal without another explanation call.

## Terminal Taxonomy

Known zero-call outcomes include confirmed auth/MFA/captcha/bot wall, explicit no availability,
proven property/date/occupancy conflict, persistent rendered currency mismatch, grounded candidate
rejection, unsafe/external/protected/additional popup, unavailable observation, provider/key/rate
limit, job/day/call/time limit, and sanitized infrastructure failure.

Ambiguous outcomes include missing selectors, unknown property-card layout, unverified inventory
scope/pagination/detail, empty/invalid extraction, and safe-control no-progress. If unresolved after
Sonnet and eligible Opus diagnosis, return a maintenance-capable terminal diagnosis rather than a
generic failure.

## Verification

- Production-shaped unit/integration fixtures cover selector/copy drift for property search,
  context, currency, room rates, inventory scope/pagination/detail, and extraction.
- Adversarial tests prove hallucinated property, dates, occupancy, currency, room, price,
  refundability, and reservation identity cannot pass code verification.
- Popup tests cover one safe relevant child and exact refusal of multiple/external/protected/mutating
  children.
- Structural tests require every registered path to end in success or a canonical diagnosis.
- Coordinator tests prove cleanup/state preservation for every terminal path and shared job-budget
  behavior across sync plus checks.
