---
unit: 002-dom-resilient-browser-workflows
bolt: 048-dom-resilient-browser-workflows
stage: design
status: complete
updated: 2026-08-15T22:56:03Z
---

# Technical Design - Server-Backed Remote Authentication Verification

## Architecture Pattern

Keep the existing headed Playwright/noVNC login and application-owned finalization lifecycle, but
replace the `/connect` success detector with an attempt-local server-contract verifier. The
interactive page is only a cookie producer. A separate isolated request context proves whether one
immutable Booking cookie snapshot is authenticated; neither the rendered page nor a model
participates in that decision.

The v1 contract is code-owned and literal: `GET https://secure.booking.com/myaccount.html` with
redirects disabled. A fresh cookie-free context must receive the approved Booking OAuth redirect.
The same request with a candidate snapshot must return a direct, bounded `200 text/html` response
without a redirect or known challenge/error shell twice in independent clean contexts. Any response
outside those exact classes fails closed.

No schema migration or new external dependency is required.

## Layer Responsibilities

### Domain

- Add closed probe outcomes and content-free response evidence to `domain.remote_auth`.
- Add `RemoteAuthServerReceipt`, bound to attempt ID, Telegram user ID, contract version, issue and
  expiry time, keyed cookie digest, verifier code, and one-use state.
- Keep cookie material and keyed digests out of public/loggable result representations.
- Extend remote-auth failures with explicit verifier-contract, verifier-unavailable, and blocked
  server-evidence outcomes so the viewer and Telegram can provide actionable fixed guidance.

### Infrastructure verifier

- Add `BookingServerSessionVerifier` under `infrastructure.remote_auth.network_session`.
- Validate the literal contract URL at construction: HTTPS, exact Booking host/path, no query,
  fragment, credentials, or configurable/model-provided override.
- Establish a fresh empty-context negative baseline before the viewer is declared ready.
- Canonicalize only Booking-domain cookies into stable JSON bytes, retaining the exact values solely
  in attempt memory and the successful encrypted session write.
- Stabilize and deduplicate keyed fingerprints; a snapshot is probed once except for the contract's
  required second independent positive confirmation.
- For each probe, create a fresh mobile context with service workers blocked, add only the immutable
  candidate cookies, call the literal endpoint through `context.request.get`, and always close the
  context. Page routes are not treated as protection for API requests.
- Read at most a small bounded prefix of the response body in memory to reject known login,
  challenge, and error shells. Never log, persist, or send bodies, headers, queries, cookie values,
  principals, or reservation data.
- Issue a short-lived receipt only after the required baseline and two positive probes.

### Remote browser runner

- Preserve Xvfb, x11vnc, websockify, mobile Chromium, navigation/download guards, cancellation,
  expiry, and process cleanup.
- Remove `body.inner_text`, page-state assessment, inventory navigation, DOM-step declaration,
  semantic receipt, and Sonnet/Opus capability creation from `/connect`.
- Poll only the BrowserContext cookie jar. After the same new Booking snapshot is observed twice,
  call the server verifier. An explicit signed-out result keeps the viewer open; no model call or
  incident is made.
- On verified evidence, consume the receipt against the same attempt/caller/contract/snapshot,
  serialize those exact candidate bytes, admit existing finalization, and return success. Never
  recapture cookies after verification.
- Contract drift, external redirect, or bounded transport exhaustion returns a typed failure after
  cleanup. Contract evidence stays content-free.

### Application and composition

- Keep `RemoteAuthenticationManager` as the sole owner of finalization precedence, encrypted import,
  session replacement, cancellation, purge/revocation, notification, and active-browser admission.
- Compose the verifier factory directly in `build_remote_auth_runtime`; remove the adaptive runtime
  scope and `BrowserJobKind.REMOTE_AUTH` admission from `/connect`.
- Preserve the previous saved session on every baseline/probe/receipt/persistence failure.
- Render explicit fixed messages for contract maintenance and temporary server verification failure.
- Record maintenance evidence only after browser/display cleanup and only for contract drift. The
  evidence contains contract version plus closed status/media/redirect/size classes; it never
  contains model attempts or browser structure.

## Contracts

### Server Contract v1

```text
method: GET
url: https://secure.booking.com/myaccount.html
redirects: disabled

signed out:
  status = 302
  media = text/html
  location host = account.booking.com
  location path = /auth/oauth2

authenticated:
  status = 200
  media = text/html
  no Location header
  body within configured bound
  no bounded challenge/login/error-shell signature
```

Status, URL, media type, cookie presence, and cookie names are insufficient independently. The full
contract, including the fresh negative baseline and two independent positive probes of the same
bytes, is required.

### Receipt Admission

```text
fresh signed-out baseline
  + stable immutable candidate snapshot
  + isolated positive probe #1
  + isolated positive probe #2
  -> issue receipt(attempt, caller, v1, HMAC(snapshot), TTL)
  -> validate and consume once against exact snapshot
  -> enter existing FINALIZING critical section
  -> encrypt exact snapshot
```

A receipt mismatch, expiry, replay, caller/attempt substitution, or snapshot change returns a typed
failure and cannot enter persistence.

### Failure Mapping

| Evidence | Outcome | User behavior | Incident/model |
|----------|---------|---------------|----------------|
| Exact signed-out contract | `SIGNED_OUT` | Keep viewer open | None; zero model calls |
| Exact signed-in contract twice | `AUTHENTICATED` | Finalize and close | None |
| Known challenge/rate-limit response | `CHALLENGE` | Keep open for interactive challenge or bounded retry | None |
| External/unapproved redirect | `BLOCKED_REDIRECT` | Fail closed | Content-free fixed reason |
| Unknown bounded response/schema | `CONTRACT_CHANGED` | Fail with maintenance guidance | Content-free owner incident |
| Timeout/5xx/network exhaustion | `UNAVAILABLE` | Fail with retry guidance | Fixed infrastructure reason |
| Cancel/expiry/purge/shutdown | Existing lifecycle result | Existing behavior | Existing suppression policy |

## Security and Privacy

- The verifier URL, method, redirect policy, and response predicates are code constants, not config,
  page, response, or model input.
- Only exact Booking-domain cookies cross into isolated probes; no local storage, page JS, service
  worker, cache, request history, or DOM is copied.
- Cookie values and their HMAC never enter logs, incidents, exceptions, Telegram, model prompts, or
  test snapshots. HMAC comparison is constant-time.
- The receipt is attempt-local and one-use. Its HMAC key is generated in memory for the runner
  attempt and destroyed with the verifier.
- API request contexts bypass Playwright page routing, so literal URL validation and disabled
  redirects are mandatory at the verifier boundary.
- The interactive context still blocks non-Booking top-level navigation and downloads. This change
  does not authorize Google/Apple/external sign-in or any transaction.

## Reliability and Observability

- Baseline failure prevents the browser from being advertised ready, avoiding a flow that can never
  prove success.
- Candidate stabilization avoids probing transient login cookie churn; keyed fingerprints suppress
  repeat probes without exposing secret-derived values.
- Explicit signed-out evidence is nonterminal and does not reset or reload the user-visible page.
- Each isolated probe closes in `finally`; runner cleanup remains idempotent for all terminal paths.
- Logs contain only attempt-safe outcome codes and exception class names. Contract drift evidence
  contains only closed classes and the public contract version.

## Test Design

### Verifier unit tests

1. Fresh baseline accepts only the exact signed-out redirect and rejects direct 200, wrong host/path,
   query-derived destination authority, wrong media, malformed headers, and external redirects.
2. Two exact isolated authenticated responses issue one receipt; status-only, URL-only, cookie-only,
   DOM-only, login shells, challenge shells, oversized bodies, redirects, 429, 5xx, timeout, and
   malformed responses do not.
3. Both positive probes receive byte-identical candidate cookies; only Booking-domain cookies are
   copied; service workers are blocked; GET and `max_redirects=0` are asserted; every context closes.
4. Receipt rejects wrong attempt/caller/contract/snapshot, stale time, and reuse.
5. Safe results and logs contain no cookie values, body text, headers, query strings, user identity,
   reservation content, or keyed digest.

### Runner and composition tests

1. A stable post-login cookie snapshot reaches verification and exact-snapshot finalization without
   any locator, page classifier, inventory navigation, or LLM budget/session.
2. Repeated signed-out snapshots keep the viewer open without reload; a later stable authenticated
   snapshot succeeds.
3. Missing/stale receipts, snapshot changes, contract drift, blocked redirect, transport failure,
   cancellation, expiry, process death, capture rejection, purge, and shutdown remain fail-closed.
4. Cookies are serialized only after receipt consumption and are not recaptured from the interactive
   context.
5. Browser/Playwright/display cleanup precedes incident publication and notification.
6. Registry coverage no longer treats `/connect` capture as a DOM step; ordinary saved-session
   validation, inventory, and search remain registered.

### Repository gate

- Focused verifier/runner/application/runtime/registry tests.
- Ruff, strict mypy, full pytest, CLI smoke, AI-DLC validators, and `git diff --check`.

## ADR Analysis Input

This changes the success authority selected by ADR-026 and ADR-032 for `/connect`, while retaining
their remote-browser transport, protected navigation, and saved-session verification constraints.
It is a durable security and architecture decision and therefore requires ADR-035.
