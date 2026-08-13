---
unit: 002-dom-resilient-browser-workflows
bolt: 042-dom-resilient-browser-workflows
stage: design
status: complete
updated: 2026-08-13T02:39:01Z
---

# Technical Design - DOM Step Registry and Page-State Classification

## Architecture

Add a provider-neutral resilience domain and application registry/controller. Browser adapters
produce a bounded fresh observation. Deterministic classification runs first. Only an ambiguous
state receives the caller-scoped `AdaptiveModelSession` and `BrowserJobCostBudget` established by
Bolt 041.

```text
fresh browser observation
        |
        v
protected-first deterministic classifier
   | known                         | ambiguous
   v                               v
exact mapped stop, zero calls      Sonnet typed classification
                                   |
                                   +-- valid/confident -> guarded code mapping
                                   `-- invalid/unknown -> eligible Opus classification
                                                            |
                                                            v
                                                  exact typed terminal/result
```

## Layer Changes

### Domain

- Add `domain/browser_resilience.py` with closed journey/step/state/capability/evidence/action types,
  validated classifications, definitions, and code-verification receipts.
- Keep raw selectors, page content, URLs, model responses, Playwright objects, and workflow-specific
  repositories outside these types.

### Application

- Add `application/browser_resilience.py` with the immutable `DOM_STEP_REGISTRY`, deterministic
  classification, adaptive page-state resolver, and total outcome mappings.
- Each production workflow exports its exact `DOM_STEPS` tuple. A structural test compares those
  declarations with registry membership and validates every definition.
- Add narrow profile-aware classifier and fresh-observation ports without changing legacy test
  fakes into mandatory adaptive implementations.

### Infrastructure

- Add a shared bounded page-state assessment in `infrastructure/browser/page_state.py` and refactor
  Playwright authentication checks to consume it.
- Replace weak `has_authenticated_account_context` behavior: Genius/header/bookings-link evidence is
  inconclusive; login/MFA/captcha evidence has priority.
- Add a strict tool/schema-only Anthropic page classifier accepting an admitted profile. It emits
  allowlisted state/evidence/action fields only and performs no browser action.
- Do not send screenshots or typed control values from possible credential/MFA pages.

### Workflow Integration

- Remote auth uses `BrowserJobKind.REMOTE_AUTH`; repeated polling is deterministic. Stable ambiguous
  evidence may classify once and a model-authenticated candidate must pass a fixed read-only account
  probe before cookie capture.
- Inventory preserves classifier/agent authentication and captcha results through
  `InventoryDiscoveryResult` and `SynchronizationFailureCode`, removing the current
  `authentication_required -> gave_up -> navigation_failed` collapse.
- Search performs protected-first classification before fallback and postflight. A model conclusion
  cannot refresh a session.
- The coordinator owns one job budget for `/bookings`, `/checknow`, scheduled slots, or remote auth
  and shares it with every nested role. Exact auth marks only the current session revision and sends
  existing `/connect` guidance.

## Registry Contract

Every `DomStepDefinition` declares:

- one stable `DomStepId` and `DomJourney`;
- deterministic postcondition name;
- safe capability set, empty for protected/diagnosis-only steps;
- protected-state set;
- typed semantic schema or explicit diagnosis-only mode;
- adaptive recovery policy;
- total mappings for known page states, model stops, provider/cost stops, observation failure, and
  exhausted ambiguity.

Definitions use fixed codes rather than dynamic strings such as inventory scope names. Scope and
pagination context are typed inputs to a stable step.

## Classifier Contract

The deterministic classifier applies this precedence to one fresh observation:

1. observation unavailable;
2. external/unapproved or mutating/prohibited destination;
3. captcha/bot challenge;
4. MFA/OTP/passkey/security challenge;
5. login/password/credential/signup;
6. strong supported inventory/search/property structure;
7. weak account chrome alone remains ambiguous.

The model request contains only bounded visible structure/text and the named step. The response is a
strict typed class, confidence, evidence categories/references, and operator action. Any selector,
script, URL, free-form action, credential value, or unsupported enum makes the response invalid.

## Adaptive Resolution

- `PageStateResolver` receives the shared job budget; it never creates a new allowance.
- `AMBIGUOUS` starts Sonnet with role `CLASSIFICATION` and a code-owned token envelope.
- Invalid schema or low-confidence/unknown output reconciles as a quality failure and may select
  Opus under the same session/caller/budget.
- Provider authentication/outage/rate-limit, job/day/time ceilings, observation loss, protected
  destination, and deterministic auth/captcha are terminal and never receive explanation-only
  calls.
- Each admitted physical provider call is reserved and reconciled exactly once.

## Authentication Safety

`PageStateClassification(AUTHENTICATED_CANDIDATE)` has no authority to:

- serialize or refresh cookies;
- extend session expiry;
- prove account/inventory identity;
- click/fill a credential, MFA, captcha, account-setting, cancellation, modification, checkout,
  payment, or purchase control.

A `CodeVerificationReceipt` is created only after deterministic strong supported-page evidence or a
fixed guarded read-only probe completes on the approved Booking.com origin.

## Error Mapping

Central mappings preserve exact reasons:

- authentication/MFA -> auth-required plus appropriate operator action;
- captcha/bot wall -> bot-wall;
- protected/prohibited/external -> blocked action/destination;
- provider auth/outage/rate-limit -> typed LLM/provider result;
- job/day/time -> budget/time result;
- observation unavailable -> observation result;
- unresolved model quality -> typed ambiguity/maintenance diagnosis, not generic `gave_up`.

## Data and Configuration

Bolt 042 adds no schema or model-selection configuration. It consumes schema v14, approved profiles,
cost types, same-caller factory, and `BrowserJobKind.REMOTE_AUTH` from Bolt 041. Registry definitions,
thresholds, and prompt versions are code-owned.

## Test Design

- Pure domain tests validate definitions, protected capability bans, classification bounds, and
  verified-receipt authority.
- Structural tests compare exact production `DOM_STEPS` declarations with registry membership and
  require total terminal mappings.
- Browser tests cover changed login DOM retaining Genius/header/bookings links, coexisting
  login/account markers, MFA/passkey/captcha, supported inventory proof, and external/mutating URLs.
- Resolver tests prove deterministic known states consume zero models/ledger rows and ambiguity uses
  ordered Sonnet then eligible Opus.
- Remote-auth tests prove model-only authenticated never saves cookies and polling does not create
  repeated calls.
- Inventory/coordinator regression tests prove model authentication becomes auth-required, marks the
  exact session revision, sends `/connect` guidance once, and never refreshes cookies from the model.
