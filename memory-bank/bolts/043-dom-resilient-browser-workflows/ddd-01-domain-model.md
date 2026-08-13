---
unit: 002-dom-resilient-browser-workflows
bolt: 043-dom-resilient-browser-workflows
stage: model
status: complete
updated: 2026-08-13T02:39:01Z
---

# Static Model - Semantic DOM Recovery and Terminal Diagnosis

## Bounded Context

This context converts ambiguous current-page evidence into guarded read-only progress, positive
semantic observations, or a precise terminal diagnosis across inventory and price-search journeys.
It consumes Bolt 041 routing/budgets and Bolt 042 step/page classifications. It does not create a
second router, accept model claims as booking truth, prove negative inventory/completeness, or
perform reservation/account/payment mutations.

## Domain Entities

| Entity | Properties | Business Rules |
|--------|------------|----------------|
| `ResilienceEpisode` | step definition, fresh observations, ordered model attempts, guarded actions, verifier results, terminal diagnosis | One named step; one shared job budget; every executed action is code-authorized and followed by a fresh verifier |
| `SemanticStepObservation` | step ID, positive facts, visible evidence, source observation identity | Only allowlisted positive facts grounded in the current observation; never authoritative absence, completeness, equivalence, eligibility, or safety claims |
| `StepVerificationResult` | verified, ambiguous, or exact failure; evidence categories; optional code receipt | Only code can return verified or exact domain failure |
| `TerminalBrowserDiagnosis` | exact code, step, provenance, confidence, safe evidence categories, operator action, maintenance flag | Total typed result; no raw page/model/exception data; known failures retain deterministic provenance |
| `PopupAdoptionResult` | adopted page receipt or exact refusal | At most one new read-only Booking.com popup relevant to the current step |

## Value Objects

- `SemanticFactKey`: property identity, stay dates, occupancy, currency, room/rate content,
  inventory scope, pagination progress, reservation identity, refundability evidence.
- `VisibleEvidence`: bounded current element reference or literal visible excerpt; never input value,
  cookie, query, credential, or hidden content.
- `DiagnosisProvenance`: deterministic, Sonnet recovered, Sonnet diagnosed, Opus diagnosed, policy
  stop, provider stop, budget stop, infrastructure stop.
- `PopupRefusalReason`: none/multiple, external, protected, mutating, irrelevant, unsupported,
  observation unavailable.

## Aggregates and Invariants

1. Model facts are advisory positive observations. Existing domain services compare them with trusted
   booking/session inputs before accepting progress or offers.
2. A selector miss, unknown layout, unverified inventory scope/pagination/detail, empty/invalid
   extraction, or safe-control no-progress is ambiguous rather than a proven business failure.
3. Confirmed authentication/MFA/captcha, explicit unavailable, trusted context conflict, persistent
   currency mismatch, deterministically rejected valid candidates, blocked destinations/actions,
   provider/budget/time/observation/infrastructure stops are exact and receive no diagnosis call.
4. Sonnet may recover or interpret; eligible unresolved quality failure may reach one Opus
   diagnosis-only attempt. Opus never gains broader action capability.
5. A popup is adopted only after infrastructure verifies exactly one fresh HTTPS Booking.com child,
   an allowlisted read-only route relevant to the step, and no protected/mutating classification.
6. Every terminal registered path returns `TerminalBrowserDiagnosis`; generic unknown/navigation/
   extraction/gave-up fallthrough is forbidden.
7. All failures preserve prior safe reservations/opportunities and release browser/coordinator
   resources.

## Story Coverage

- **US-135**: semantic observation, code verifier, capability-aware recovery, guarded popup adoption,
  and model-assisted positive inventory/offer evidence.
- **US-136**: canonical terminal diagnosis, deterministic zero-call taxonomy, diagnosis-only Opus,
  and total reason propagation.
