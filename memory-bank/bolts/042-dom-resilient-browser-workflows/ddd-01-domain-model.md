---
unit: 002-dom-resilient-browser-workflows
bolt: 042-dom-resilient-browser-workflows
stage: model
status: complete
updated: 2026-08-13T02:39:01Z
---

# Static Model - DOM Step Registry and Page-State Classification

## Bounded Context

This context identifies every production Booking.com operation whose correctness depends on the
current DOM, classifies the current page with protected-state precedence, and maps the outcome to an
exact workflow reason. It does not decide model routing or cost, prove booking equivalence or
inventory completeness, mutate a reservation/account, enter credentials, or persist incidents.

## Domain Entities

| Entity | Properties | Business Rules |
|--------|------------|----------------|
| `DomStepDefinition` | stable step ID, journey, deterministic postcondition, safe capabilities, protected states, semantic schema, recovery policy, terminal mappings | Every production DOM-sensitive seam has exactly one definition; protected steps expose no action capability; mappings are total |
| `PageStateClassification` | state, confidence, evidence categories/references, operator action, provenance | Contains only bounded allowlisted observations; never selectors, scripts, input values, raw URLs, or page text |
| `PageStateResolution` | classification, exact stop, code-verification receipt | Model-authenticated is only a candidate; only deterministic supported-page proof can produce a verified receipt |

## Value Objects

| Value Object | Values / Constraints |
|--------------|----------------------|
| `DomJourney` | remote auth, session validation, account inventory, price search |
| `DomStepId` | explicit closed identifiers for remote auth/session, inventory traversal/extraction/completeness, production search/property/context/currency/snapshot/extraction |
| `PageState` | auth required, MFA required, captcha, bot wall, external, prohibited, authenticated candidate, verified authenticated, inventory, search results, property, unsupported, ambiguous |
| `PageStateSource` | deterministic, Sonnet, Opus |
| `EvidenceCategory` | allowlisted structural evidence such as credential control, MFA control, captcha challenge, weak account chrome, supported inventory/search/property structure, destination class, or unavailable observation |
| `DomCapability` | allowlisted read-only operation categories; never arbitrary selector/script/action authority |
| `OperatorAction` | none, connect, complete MFA, retry later, maintain code |
| `CodeVerificationReceipt` | named supported state, step ID, fresh-observation identity; cannot be model-created |

## Aggregates

| Aggregate Root | Members | Invariants |
|----------------|---------|------------|
| `DomStepRegistry` | all `DomStepDefinition` values | Exact production step declarations equal registry membership; every definition has a deterministic postcondition and total terminal mapping |
| `PageStateResolution` | fresh observation assessment, optional model attempts, code receipt, exact terminal | Deterministic protected/known state wins; ambiguity alone admits a model session; model output never becomes authenticated truth |

## Domain Services

| Service | Operation | Rule |
|---------|-----------|------|
| `DeterministicPageClassifier` | classify a fresh bounded observation | Protected-state precedence: unavailable, external/prohibited, bot wall, MFA, login, strong supported page, then ambiguous; weak account chrome cannot prove authentication |
| `PageStateResolver` | resolve a step using deterministic classification and optional adaptive classification | Known state returns with zero calls; ambiguity may use Sonnet then eligible Opus through Bolt 041 policy |
| `TerminalOutcomeMapper` | map page/model stops to inventory/search/session outcomes | Auth, captcha, provider, budget, observation, and safety codes are preserved without generic fallthrough |

## Protected-State Rules

1. Observation unavailable, external destinations, and prohibited/mutating destinations terminate
   under their exact code before model action.
2. Captcha/bot-wall evidence outranks weak authenticated chrome.
3. MFA/passkey/security-challenge evidence outranks weak authenticated chrome.
4. Login/password/credential/signup evidence outranks weak authenticated chrome.
5. Only strong supported account/inventory evidence can deterministically prove authentication.
6. A model can classify a protected page for ambiguity resolution, but cannot click, fill, submit,
   save cookies, or extend a session there.

## Production Step Coverage

- Remote auth: session capture and session validation.
- Inventory: entry, readiness, scope, pagination, detail, extraction, completeness.
- Price search: form/results entry, consent overlay, property locate/open, context, room/rate
  readiness, currency, snapshot, and offer extraction.
- Legacy search-home/form automation does not count toward coverage of the production
  `BookingComSearchMonitor` path.

## Business Rules and Invariants

1. A conclusive known state constructs no adaptive session, resolves no caller key, reserves no
   spend, and invokes no model.
2. Only `AMBIGUOUS` current page state can construct a classifier session.
3. Sonnet classification is first; Opus is eligible only for invalid schema or unresolved/low
   confidence under Bolt 041's shared job budget.
4. A model-authenticated classification can permit only a fixed guarded read-only probe.
5. Cookies are saved/refreshed only from a code-verification receipt produced by a fresh supported
   workflow, never by weak selectors or model confidence.
6. `AUTHENTICATION_REQUIRED` maps to the domain auth-required result, marks the exact session
   revision for reauthentication, and produces `/connect` guidance rather than `gave_up`.
7. Registry definitions contain capability categories, not raw selectors or model-provided actions.
8. Domain truth such as reservation absence/completeness and offer equivalence remains code-owned.

## Story Coverage

- **US-133**: exhaustive `DomStepRegistry`, stable IDs, structural coverage, capabilities, and total
  mappings.
- **US-134**: protected-first deterministic classifier, adaptive ambiguity resolution, verified
  authentication receipt, and exact outcome propagation.
