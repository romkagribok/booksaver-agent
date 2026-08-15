---
id: 006-verify-remote-authentication-from-server-evidence
unit: 002-dom-resilient-browser-workflows
intent: 022-adaptive-booking-browser-resilience
status: complete
priority: must
created: 2026-08-15T22:33:19.000Z
assigned_bolt: 048-dom-resilient-browser-workflows
implemented: true
---

# Story: Verify Remote Authentication from Server Evidence

## User Story

**As a** BookSaver user completing Booking.com authentication
**I want** `/connect` to verify my session from Booking.com's server response rather than reservation-page DOM
**So that** presentation changes cannot prevent a genuine login from being saved

## Acceptance Criteria

- [ ] **Given** a new transient login attempt, **When** BookSaver establishes its verifier baseline,
  **Then** a fresh cookie-free isolated context must receive the versioned signed-out response from
  one fixed HTTPS Booking.com read-only account endpoint before the viewer is admitted.
- [ ] **Given** the interactive browser's Booking cookie state changes, **When** the candidate is
  stable and has not already been tested, **Then** BookSaver verifies exactly that immutable cookie
  snapshot in fresh service-worker-free isolated contexts without submitting credentials or loading
  reservation inventory.
- [ ] **Given** both isolated probes return the exact signed-in network contract, **When** code binds
  the result to the attempt, caller, contract version, expiry, and keyed cookie-snapshot digest,
  **Then** a single-use server-authentication receipt may enter the existing atomic finalization flow.
- [ ] **Given** only a signed-in-looking URL, cookie name/change, visible account chrome, reservation
  DOM, screenshot, or model classification, **When** the server contract is not satisfied, **Then** no
  receipt is issued and no session is saved.
- [ ] **Given** the fixed probe explicitly returns the signed-out contract, **When** the user has not
  finished authentication or entered invalid credentials, **Then** the viewer remains available and
  BookSaver makes no LLM call merely to explain the predictable result.
- [ ] **Given** an external redirect, challenge, transport failure, oversized or wrong-media response,
  or changed response contract, **When** bounded verification cannot prove authentication, **Then**
  BookSaver fails closed with a typed reason, preserves the prior saved session, and records only
  content-free maintenance evidence when the contract changed.
- [ ] **Given** verification succeeds, **When** finalization begins, **Then** the exact verified cookie
  snapshot—not a later recapture—is encrypted before committed success, Telegram notification, or
  viewer close, while purge/revocation and daemon shutdown remain authoritative.
- [ ] **Given** any `/connect` outcome, **When** logs, incidents, model prompts, and persisted data are
  inspected, **Then** response bodies, headers, query strings, cookie values, tokens, principals,
  account data, and reservation data are absent.
- [ ] **Given** ordinary authenticated, signed-out, and challenge outcomes, **When** `/connect` runs,
  **Then** authentication success uses zero model calls and no model budget; models cannot issue,
  veto, or replace the server-authentication receipt.

## Technical Notes

- Version 1 probes literal `GET https://secure.booking.com/myaccount.html` with redirects disabled.
  A fresh context must receive the exact Booking OAuth redirect; a candidate must receive the exact
  bounded direct account response twice from independent contexts.
- Cookie changes are admission triggers only. The response contract is the authority.
- Keep the existing finalizing lock, encrypted session vault, purge revocation, and viewer-success
  ordering from US-140.

## Dependencies

### Requires

- US-134, US-136, and US-140.
- Bolts 042, 044, 046, and 047.

### Enables

- Reliable DOM-independent `/connect` completion and later inventory synchronization.

## Edge Cases

| Scenario | Expected Behavior |
|----------|-------------------|
| Anonymous cookies have SSO-like names | Negative server probe wins; no receipt |
| Signed-out and signed-in page URLs are identical | Exact protected-resource response contract decides |
| One candidate probe passes and the second fails | No receipt; preserve prior session |
| Service worker or page JavaScript fakes state | Isolated request context ignores it |
| Candidate cookies mutate after verification | Digest mismatch rejects finalization |
| User purge races verification | Revocation wins and state cannot be recreated |
| Booking changes the endpoint contract | Typed maintenance incident; no model-authenticated success |

## Out of Scope

- Reservation inventory parsing, completeness, identity, or reconciliation.
- Treating internal Booking endpoints as stable beyond the explicit versioned contract.
- Persisting candidate sessions before successful verification.
- Sending server responses or session material to an LLM.
