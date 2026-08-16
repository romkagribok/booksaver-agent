---
stage: design
bolt: 049-dom-resilient-browser-workflows
created: 2026-08-16T16:27:00Z
---

# Technical Design: Contract-v2 Edge-Pending Negative Control

## Architecture Pattern

Retain the attempt-local, deterministic, server-backed verifier from ADR-035. This correction is a
closed response-classification amendment, not a new authentication mechanism, endpoint, model path,
or persistence flow.

## Layer Responsibilities

- **Domain**: require contract-v2 evidence and receipt identifiers; preserve the invariant that only
  `AUTHENTICATED` carries a receipt.
- **Infrastructure verifier**: classify one additional exact negative tuple after response body and
  protected URL validation. Keep redirects disabled and retain isolated contexts.
- **Remote browser runner**: reuse the existing `SIGNED_OUT` path. Baseline `SIGNED_OUT` admits the
  viewer; candidate `SIGNED_OUT` schedules the bounded same-snapshot recheck.
- **Incident operations**: version the verifier category so new evidence cannot be confused with v1.
- **Operator documentation**: describe both negative controls and the unchanged positive contract.

## Exact Classification Order

1. Reject external redirects, rate limits, server errors, oversized declared responses, and
   unreadable responses under their existing typed outcomes.
2. Preserve exact `302 text/html` Booking OAuth redirect as `SIGNED_OUT`.
3. Read a bounded body and reject known challenge markers before accepting any direct response.
4. Parse and require the exact HTTPS `secure.booking.com/myaccount.html` response URL with no query
   or fragment.
5. Classify exactly `202 text/html`, no redirect, empty body, exact URL as `SIGNED_OUT`.
6. Preserve exactly `200 text/html`, no redirect, bounded non-empty body, exact URL as
   `AUTHENTICATED`.
7. Classify every other tuple as `CONTRACT_CHANGED`.

The `202` predicate is deliberately non-general: status class `2xx`, empty body alone, or a Booking
URL alone is insufficient.

## Contract Versioning

- `SERVER_CONTRACT_VERSION`: `booking-account-session-v2`.
- Receipt verifier: `booking_server_session_v2`.
- Incident verifier category: `remote_auth_server_contract_v2`.
- Contract v1 receipts are attempt-local and ephemeral, so no persisted migration is required.
- SQLite schema remains v15.

## Security Design

- The new tuple can only return `SIGNED_OUT`; domain validation forbids a receipt on that outcome.
- Candidate `202` never reaches finalization and never snapshots cookies for persistence.
- Positive receipt issuance remains two clean contexts using identical immutable candidate bytes.
- No response content, headers, URL, cookie material, account identity, or model prompt crosses the
  verifier boundary; only existing closed evidence classes are logged or retained.
- DOM, visible URL state, cookies, and models remain triggers/non-authorities.

## Test Design

1. Baseline exact `202` establishes the negative control and allows candidate verification.
2. Candidate exact `202` returns `SIGNED_OUT`, has no receipt, and runner rechecks after the bounded
   quiet interval rather than terminating.
3. `202` with non-empty body, wrong media, redirect, wrong path/host, query, fragment, challenge,
   oversized content, or unavailable body never authenticates.
4. OAuth redirect remains signed out.
5. Two exact `200` bounded responses remain the sole receipt path; one positive plus one `202` does
   not issue a receipt.
6. Contract-v1 evidence/receipt identifiers are rejected by v2 domain types.
7. Content-free incident and notification tests use the v2 verifier category.
8. Full remote-auth, persistence, Telegram, lint, type, AI-DLC, and repository regressions remain
   green.

## Deployment and Rollback

No schema or configuration change. Build and stage an exact image, retain the current image plus
online SQLite/config/environment backups, recreate only BookSaver, and require live `/connect`
acceptance after deployment. Image rollback is sufficient for runtime regression; database restore
still requires separate data-loss approval.
