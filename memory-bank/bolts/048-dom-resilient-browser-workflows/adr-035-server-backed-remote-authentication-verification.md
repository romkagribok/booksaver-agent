---
bolt: 048-dom-resilient-browser-workflows
created: 2026-08-15T22:56:03Z
status: accepted
amends: ADR-026
supersedes: ADR-032 decision 3 for /connect success only
---

# ADR-035: Server-Backed Remote Authentication Verification

## Context

`/connect` originally inferred authentication from rendered Booking account/inventory structure and
later added Sonnet/Opus classification plus code-grounded DOM receipts. Booking changed the mobile
reservation page repeatedly. A user could be visibly logged in while BookSaver either reloaded the
page, waited until timeout, or tore down the viewer after both models rejected unfamiliar structure.
The failure was not credential or session persistence: success authority was coupled to a
presentation surface that does not define whether Booking's server accepts the session.

Chromium exposes no trusted `isLoggedIn()` primitive. Cookie presence, cookie names, the visible URL,
and a 2xx response on an unprotected page are also insufficient because anonymous Booking sessions
receive cookies and some account-looking pages render the same URL/status when signed out.

Content-free live discovery established a usable current server distinction: a cookie-free request
to the fixed protected account endpoint redirects to Booking OAuth, while the same request with an
authenticated session returns the protected resource directly.

## Decision

1. Make a versioned, code-owned, read-only Booking server contract the sole `/connect` authentication
   authority. Contract v1 is `GET https://secure.booking.com/myaccount.html` with redirects disabled.
2. Require a fresh cookie-free isolated context to match the exact signed-out Booking OAuth redirect
   before accepting any candidate in an attempt.
3. Treat a stable immutable Booking cookie snapshot as a trigger only. Require two independent clean
   contexts holding exactly that snapshot to match the direct bounded signed-in response.
4. Issue a short-lived, single-use receipt bound to attempt, Telegram caller, contract version, and a
   keyed HMAC of the exact cookie bytes. Existing finalization may persist only those bytes after the
   receipt is validated and consumed.
5. Remove reservation DOM, page text, selectors, visible URL inference, inventory navigation, and
   Sonnet/Opus classification from `/connect` success authority. Models cannot create, veto, or
   explain ordinary signed-out evidence.
6. Fail closed on contract drift, external redirect, challenge, transport exhaustion, receipt
   mismatch, cancellation, expiry, purge/revocation, or persistence failure. Preserve the previously
   saved session on every failure.
7. Permit only content-free closed server-evidence classes in logs and maintenance incidents. Never
   retain response bodies, headers, queries, cookie values/digests, principals, or reservation data.
8. Keep ADR-032 for saved-session validation, account inventory, and price search. Only its decision
   that `/connect` capture needs strong account/inventory page evidence is superseded.

## Rationale

Authentication is a server authorization fact, not a UI-layout fact. A negative control prevents an
endpoint that has become public or contaminated from proving every session. Independent positive
probes remove page JavaScript, service workers, cache, and transient browser state from the decision.
Binding the receipt to exact bytes closes the gap between what was verified and what is encrypted.

The chosen endpoint is not a public stable Booking API, so it remains versioned and fail-closed. That
maintenance burden is materially narrower than tracking arbitrary reservation DOM and cannot be
silently weakened to URL, cookie, or model heuristics.

## Alternatives Considered

1. **Continue improving DOM/LLM classification**: rejected; it still makes presentation layout an
   authentication authority and repeated production changes demonstrated the brittleness.
2. **Accept any Booking auth-looking cookie**: rejected; anonymous sessions receive overlapping
   cookie names and cookie presence does not prove server authorization.
3. **Accept the post-login URL or any direct 2xx**: rejected; unprotected/account-looking pages can
   retain URLs and statuses while signed out, challenged, or rendering an error shell.
4. **Use browser local storage or JavaScript state**: rejected; both are page-controlled,
   presentation-dependent, and easier to spoof or drift than the protected server response.
5. **Use an undocumented identity JSON endpoint**: none was observed during safe discovery. Inventing
   one without a negative and positive control would weaken the proof.
6. **Require manual operator confirmation**: safe but rejected as the normal path because it restores
   the phone/VPS support burden `/connect` was created to remove. It remains a break-glass option if
   Booking removes every usable read-only server distinction.

## Consequences

### Positive

- Mobile reservation DOM changes no longer prevent `/connect` from recognizing a valid session.
- Ordinary signed-out and failed-credential states remain interactive, deterministic, and free of
  LLM cost.
- The encrypted snapshot is exactly the server-verified snapshot.
- Contract failure becomes explicit maintenance work instead of an unexplained black viewer or
  timeout.

### Negative

- BookSaver depends on one undocumented but versioned protected-resource response contract.
- A Booking response/redirect/content-policy change requires a code update before new sessions can be
  accepted.
- The verifier adds isolated requests and candidate stabilization after interactive login.

### Risks and Mitigations

- **Protected endpoint starts returning 200 to signed-out users**: mandatory fresh negative baseline
  fails closed before the viewer can succeed.
- **A 200 challenge/error shell resembles success**: bounded media/size and known shell rejection plus
  two clean probes; unknown responses are maintenance-required, never success.
- **Snapshot substitution between proof and persistence**: HMAC-bound one-use receipt and exact
  immutable serialization at finalization.
- **Cookie or response leakage**: values/bodies/headers/queries remain attempt-local; only closed
  evidence enums cross log/incident boundaries.
- **Probe URL bypasses page navigation guard**: literal HTTPS host/path validation, GET only,
  redirects disabled, and no input from config/page/model.

## Related

- **Stories**: US-141
- **ADRs**: ADR-024, ADR-025, ADR-026, ADR-031, ADR-032, ADR-033, ADR-034
