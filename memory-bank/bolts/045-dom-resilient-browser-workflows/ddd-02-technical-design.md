---
unit: 002-dom-resilient-browser-workflows
bolt: 045-dom-resilient-browser-workflows
stage: design
status: complete
updated: 2026-08-14T02:12:00Z
---

# Technical Design - Remote Authentication DOM Recovery

## Architecture Pattern

Apply the existing protected-first resilience pipeline to `/connect` as a small episode state
machine. Deterministic verification stays first. Stable ambiguity reaches the existing
caller-scoped Sonnet/Opus resolver. A grounded Sonnet inventory candidate may trigger one fixed
read-only probe, and success must pass a pure code-owned semantic verifier before cookie capture.
Opus remains diagnosis-only.

```text
fresh remote-auth page
  |
  +-- protected/known state ----------> wait or exact typed stop, zero model calls
  |
  +-- deterministic inventory proof --> code receipt --> capture cookies
  |
  `-- weak/ambiguous --> stable fingerprint debounce
                              |
                        Sonnet typed classification
                              |
                   grounded inventory candidate
                              |
                        fixed probe once
                              |
                   fresh code/semantic verifier
                         | pass       | changed/reject
                         v            v
                    code receipt    restabilize or Opus diagnosis
```

## Layer Structure

### Domain

- Reuse `PageStateClassification`, `PageStateResolution`, evidence categories, canonical terminal
  diagnosis, and Sonnet/Opus provenance.
- Add no new persistence or public action capability.
- If a small proof value is needed, keep it typed and content-free: observation identity, approved
  destination class, proof source, and allowlisted structural categories only.

### Application

- Add a pure semantic authentication verifier that receives the model resolution, the exact fresh
  observation supplied to that resolution, and a new deterministic protected-first assessment.
- Accept only a supported inventory/authenticated-candidate class with the required allowlisted
  inventory evidence, grounded references that exist in the same observation, and no operator
  action.
- Invalid/missing/foreign evidence references are a model quality rejection, not authenticated
  proof. Reuse the existing bounded escalation policy, with Opus restricted to diagnosis-only
  authority, and return an exact maintenance diagnosis rather than polling silently.

### Infrastructure

- Replace the boolean fixed probe result with enough typed, ephemeral information to continue from
  the post-navigation page without navigating again.
- Track `probe_attempted` for the remote-auth episode. The probe may run once; redirects among
  approved Booking.com inventory aliases do not reset it.
- A grounded Sonnet candidate may consume the one fixed probe. Preserve the fresh post-probe page;
  if its fingerprint changed, discard stale model evidence and restabilize without reopening probe
  admission.
- Before accepting model-assisted proof, re-run protected-first deterministic assessment on the
  same page and confirm the approved Booking.com inventory destination.
- Emit only content-free transition telemetry: probe disposition, resolver invocation, semantic
  proof accepted/rejected, and exception class. Never log URL/query, text, labels, cookies, user IDs,
  reservation data, or model response content.

### Presentation and Operations

- Preserve the existing streamed-browser status contract and session vault write path.
- On unresolved maintenance ambiguity, return the canonical diagnosis so the existing post-cleanup
  incident sink can correlate and notify the owner.
- No Telegram copy, schema, configuration, secret, Caddy, or database migration is required.

## API Design

No external endpoint changes.

Internal contracts:

- `probe_authenticated_inventory(page) -> structured post-probe observation/result`
- `verify_remote_auth_semantic_proof(page, observation, resolution) -> StepVerificationResult`
- `run_remote_browser(...) -> RemoteBrowserResult` with the existing success/terminal diagnosis
  fields and cleanup ordering.

## Data Persistence

No schema changes. Successful sessions continue through the Fernet-encrypted per-user session vault.
Model calls continue through schema-v15 spend reservations. Eligible unresolved drift continues
through the existing encrypted incident store after browser cleanup.

## Security Design

| Concern | Approach |
|---------|----------|
| False authenticated state | Require HTTPS Booking.com inventory destination, fresh observation identity, deterministic protected-state absence, grounded current references, and multiple positive structural categories |
| Model prompt injection | Model receives no cookie/form values and cannot return selectors, scripts, URLs, or actions; output is advisory typed evidence only |
| Credential/MFA/captcha exposure | Protected-first deterministic assessment short-circuits before classification/action and suppresses protected content from model evidence |
| Infinite navigation | One fixed probe per episode; redirects never reopen probe admission |
| Cross-user session | Existing caller-scoped browser lease and encrypted vault remain unchanged; proof carries no user-selected identity |
| Diagnostic privacy | Logs/incidents retain only closed codes, provenance, attempt metadata, and sanitized structural roles |

## Reliability and Cost

- Healthy deterministic success remains zero-model.
- A selector-drifted authenticated page receives one probe and one stable adaptive sequence, not one
  navigation per second.
- Unchanged fingerprints cannot cause repeated provider calls.
- Existing USD 1/job, USD 10/deployment-day, provider, and timeout limits remain authoritative.
- Resolver or incident failures cannot prevent browser teardown or corrupt the prior saved session.

## Error Handling

| Condition | Result |
|-----------|--------|
| Deterministic auth/MFA/captcha/bot wall | Existing exact interactive/known state, zero model calls |
| Fixed probe navigation/observation unavailable | Exact observation/infrastructure result or bounded fresh retry; never an infinite silent loop |
| Grounded Sonnet semantic inventory proof | Explicit `CodeVerificationReceipt` and session capture, with assisted provenance eligible for maintenance correlation |
| Invalid/ungrounded/low-confidence Sonnet output | Existing eligible retry/Opus quality path, then exact maintenance diagnosis |
| Positive Opus classification | Diagnosis only; never a receipt or cookie capture |
| Provider/key/rate-limit or budget denial | Exact non-DOM terminal diagnosis; no false maintenance claim |
| Model candidate still fails code verification | Canonical unresolved/code-maintenance diagnosis and post-cleanup incident |

## Test Design

1. Production-shaped `/mytrips.html` with “Bookings & Trips,” scope controls, and a reservation card
   but no legacy test IDs: one fixed probe, no repeated navigation, resolver reached.
2. `/myreservations.html` redirecting to the same `/mytrips.html` fingerprint: probe admission stays
   closed and the page does not reload again.
3. Grounded Sonnet inventory classification: fresh code checks pass, cookies captured once, assisted
   provenance retained.
4. Model-only candidate with missing, stale, or invented references: no cookie capture; eligible
   escalation or exact maintenance diagnosis.
5. Deterministic login, MFA, captcha, bot wall, external, and mutating pages: zero probe/model/action.
6. Provider/budget/observation stops retain exact reason and never become DOM drift.
7. Failed resolution produces an incident only after Playwright/browser/display cleanup.
8. Regression asserts no `goto` loop and no per-second LLM calls on unchanged state.

## ADR Analysis

No new ADR is required. This design directly corrects the implementation of ADR-032's explicit
repeated-classification mitigation and applies ADR-033's grounded positive semantic evidence to the
already-registered remote-auth step. ADR-034 already defines incident handling and privacy.
