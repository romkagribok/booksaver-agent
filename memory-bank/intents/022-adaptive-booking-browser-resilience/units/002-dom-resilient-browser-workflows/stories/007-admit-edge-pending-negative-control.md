---
id: 007-admit-edge-pending-negative-control
unit: 002-dom-resilient-browser-workflows
intent: 022-adaptive-booking-browser-resilience
status: complete
priority: must
created: 2026-08-16T16:23:56.000Z
assigned_bolt: 049-dom-resilient-browser-workflows
implemented: true
---

# Story: Admit the Observed Edge-Pending Negative Control Safely

## User Story

**As a** BookSaver user starting `/connect`
**I want** the verifier to recognize Booking's exact cookie-free edge-pending response
**So that** a known negative response does not abort the login before the viewer opens

## Acceptance Criteria

- [x] **Given** a fresh cookie-free isolated context, **When** the literal protected endpoint returns
  exactly `202 text/html`, an empty body, no redirect, and the unchanged protected URL, **Then**
  contract v2 classifies it as signed-out/pending and admits the interactive viewer.
- [x] **Given** a candidate cookie snapshot, **When** either isolated probe returns that exact `202`
  response, **Then** no receipt is issued, no session is saved, and the same candidate may be
  rechecked after the existing bounded quiet interval.
- [x] **Given** a `202` with a body, wrong media, redirect, different URL, query, fragment, challenge
  marker, or oversized content, **When** it is classified, **Then** it remains a typed non-success and
  cannot authorize capture.
- [x] **Given** the original OAuth redirect negative response, **When** baseline or candidate probing
  occurs, **Then** its signed-out behavior remains unchanged.
- [x] **Given** an authenticated candidate, **When** two independent contexts receive the exact
  direct `200 text/html` bounded response for the same immutable snapshot, **Then** and only then may
  code issue the existing HMAC-bound single-use receipt.
- [x] **Given** any edge-pending response, **When** logs, incidents, or model accounting are inspected,
  **Then** no body, header, cookie value, principal, account data, or model call is present.

## Technical Notes

- Advance the contract and verifier identifiers to v2 so receipts and evidence cannot mix versions.
- Reuse `SIGNED_OUT` as the runner-visible negative outcome; the exact evidence tuple distinguishes
  OAuth redirect from edge-pending without expanding success authority.
- The observed production tuple is `202`, `text/html`, zero bytes, no redirect, exact endpoint.

## Dependencies

- US-140 and US-141.
- Bolt 048 and ADR-035.

## Out of Scope

- Accepting arbitrary 2xx responses, empty bodies, URLs, or cookie presence as authentication.
- DOM or LLM authentication inference.
- Changing the two-probe positive contract or finalization lifecycle.
