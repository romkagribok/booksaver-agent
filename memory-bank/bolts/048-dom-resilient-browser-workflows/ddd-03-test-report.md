---
unit: 002-dom-resilient-browser-workflows
bolt: 048-dom-resilient-browser-workflows
stage: test
status: complete
updated: 2026-08-15T23:16:21Z
---

# Test Report - Server-Backed Remote Authentication Verification

## Summary

- **Focused tests**: 129 passed across the server verifier, headed runner, remote-auth manager,
  DOM-registry boundary, model-free incidents, owner notification, and SQLite correlation.
- **Full repository tests**: 1,561 passed with 55 known configuration-deprecation warnings.
- **Lint**: Ruff clean across `src`, `tests`, and `scripts`.
- **Types**: Strict mypy clean across 118 source files.
- **Smoke**: CLI help succeeds with `PYTHONPATH=src`.
- **AI-DLC**: Artifact validator and status integrity report zero issues/inconsistencies across 48
  bolts and 22 intents.
- **Diff hygiene**: `git diff --check` clean.

## Live Contract Validation

The production contract was validated without printing or retaining response content, headers,
queries, cookie values, principals, or reservation data:

- A fresh local cookie-free mobile context returned the exact `signed_out / redirection / html /
  booking_oauth` negative control.
- The encrypted saved VPS cookie snapshot was decrypted only inside the existing BookSaver container
  and used in one isolated read-only probe. It returned a direct bounded `200 text/html` response,
  no redirect, and none of the bounded challenge signatures. The cookie values and response body
  never left process memory or appeared in command output.

## Acceptance Criteria Validation

- ✅ **Negative control**: Viewer admission requires a fresh service-worker-free context to match the
  exact Booking OAuth signed-out response for the literal protected account endpoint.
- ✅ **Immutable candidate**: Only Booking-domain cookies are canonicalized. The same exact bytes are
  copied to each isolated probe and later handed to persistence.
- ✅ **Independent confirmation**: Two clean positive probes are required before a receipt exists.
- ✅ **Receipt binding**: Attempt, Telegram caller, contract version, short TTL, one-use state, and
  constant-time keyed snapshot comparison are enforced before finalization.
- ✅ **No DOM/model authority**: The runner contains no locator, body-text, page-state, reservation
  navigation, model session, or remote-auth model-budget path. Structural coverage declares no
  `/connect` DOM step.
- ✅ **Signed-out behavior**: Exact signed-out evidence keeps the viewer open, performs no reload, and
  can be rechecked after a bounded delay even when Booking upgrades the same server-side session
  without changing cookie bytes.
- ✅ **Fail closed**: Wrong status/media/path, oversized response, known challenge shell, 429, 5xx,
  transport exhaustion, external redirect, baseline drift, receipt mismatch/expiry/reuse, and
  persistence failure save nothing and preserve the prior session.
- ✅ **Maintenance evidence**: Contract drift opens an immediate content-free owner incident with
  no synthetic model role and with provider/budget marked not attempted/not applicable.
- ✅ **Lifecycle safety**: Existing atomic finalization, purge/revocation, daemon shutdown,
  cancellation, terminal retention, encrypted capture, and post-cleanup incident ordering remain
  covered by the full remote-auth suite.
- ✅ **Privacy**: Reprs, logs, incidents, notifications, and tests exclude cookie values/digests,
  response content/headers/queries, attempt capabilities, principals, and reservation data.

## Issues Found and Resolved

1. **Stable-cookie server promotion**: An anonymous cookie can theoretically gain authenticated
   server state without its bytes changing. The candidate stabilizer now permits a bounded same-byte
   recheck after explicit signed-out/challenge evidence; the server response remains authority.
2. **Volatile non-auth cookies**: Exact equality could starve verification if Booking continuously
   rotates telemetry cookies. After a bounded number of unstable observations, the latest immutable
   snapshot is probed twice and can be saved only if both server checks pass.
3. **Generic challenge markers**: Broad body terms could reject normal account HTML. The bounded
   guard uses only specific challenge signatures plus exact 429/status/media/redirect classes.
4. **Model-free maintenance incidents**: Existing incident invariants required a synthetic model
   role. A dedicated code-verifier diagnosis provenance now permits only the strict
   maintenance/not-attempted/not-applicable combination to create a zero-model incident.

## Remaining Human Validation

After merge, a real Telegram `/connect` remains the required human acceptance test. The expected
flow is: the viewer stays open while signed out, closes only after the server receipt enters atomic
finalization, Telegram reports connected, and the post-connect inventory refresh runs separately.
