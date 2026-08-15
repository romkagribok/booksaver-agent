---
stage: model
bolt: 046-dom-resilient-browser-workflows
created: 2026-08-14T03:10:57.000Z
---

# Static Model: Atomic Remote-Authentication Finalization

## Scope and Boundary

This model refines the existing remote-auth aggregate after code-owned page verification. It does
not change how Booking.com is classified, how cookies are obtained, or who may authenticate. The
aggregate remains one caller-bound transient browser attempt sharing the global browser lease.

## Entities

- **RemoteAuthenticationAttempt**: Identity, caller ownership, viewer capabilities, expiration,
  lifecycle state, cancellation signal, worker, and optional terminal failure. It is the aggregate
  root and serializes viewer cancellation, administrative cancellation, capture, and terminal state.
- **RemoteBrowserResult**: Terminal browser outcome containing cookies only for verified success,
  an exact safe failure only for failure, and an optional sanitized incident draft captured while
  page structure still exists.
- **VerifiedSessionCapture**: One pending code-verified cookie payload associated with the attempt.
  It is not a successful connection until encrypted persistence commits.
- **DomIncidentDraft**: Sanitized evidence prepared after model-assisted verification. It is pending
  evidence, not a recovered occurrence, until the aggregate commits the authenticated session.

## Value Objects

- **RemoteAuthStatus**: `starting`, `ready`, `connected`, `finalizing`, `succeeded`, `failed`,
  `expired`, or `cancelled`. `finalizing` is non-terminal, has no browser-control authority, and
  rejects ordinary viewer cancellation.
- **CancellationSource**: Ordinary viewer, administrative purge/revocation, daemon shutdown, or
  internal replacement. The source determines whether cancellation may cross the finalization
  boundary.
- **CodeVerificationReceipt**: Existing proof that a registered remote-auth step reached fresh
  authenticated inventory under a code verifier. Model classification alone cannot create it.
- **CaptureCommit**: Successful encrypted per-user session persistence. This is the sole event that
  permits `succeeded`.
- **FinalizationFailure**: Safe typed reason such as capture rejected, shutdown, purge/revocation,
  browser failure, or exact model/provider/policy diagnosis; it contains no cookie or page content.

## Aggregate Invariants

1. `finalizing` is entered only after a fresh `CodeVerificationReceipt` and before the runner
   publishes a success result.
2. Ordinary viewer cancellation wins before `finalizing` and is ignored during `finalizing`.
3. Administrative purge/revocation and daemon shutdown remain authoritative during `finalizing`;
   permanent revocation also prevents the repository write even if an earlier check raced.
4. A session is persisted before the attempt becomes `succeeded`, success is exposed to the viewer,
   Telegram success is sent, post-connect synchronization begins, or recovered incident evidence is
   published.
5. Capture rejection produces `failed`, never `succeeded`; the pending recovered incident draft is
   discarded and no session file is replaced.
6. A failed or cancelled attempt never carries committed cookies. A successful attempt has exactly
   one encrypted per-user session commit.
7. Browser resources and page authority are closed before encrypted capture and incident persistence.
8. Logs and ordinary state contain only lifecycle stages, typed outcomes, and safe exception class.

## State Transitions

- `starting -> ready -> connected`: existing viewer bootstrap and RFB attachment.
- `starting|ready|connected -> cancelled`: viewer cancellation, replacement, purge, or shutdown
  before verified finalization.
- `ready|connected -> finalizing`: runner presents a code verification receipt and the manager
  accepts the finalization latch.
- `finalizing -> succeeded`: browser cleanup completes, encrypted capture commits, and terminal
  state is applied.
- `finalizing -> failed`: capture is rejected or another typed finalization error occurs.
- `finalizing -> cancelled`: only administrative purge/revocation or daemon shutdown.
- Any non-terminal state may expire before finalization; `succeeded`, `failed`, `expired`, and
  `cancelled` remain terminal.

## Domain Events

- **AuthenticationFinalizationStarted**: Code verification is accepted; browser controls are no
  longer offered and viewer cancellation loses authority.
- **AuthenticatedSessionCommitted**: Encrypted session persistence succeeds and the attempt becomes
  `succeeded`.
- **AuthenticationFinalizationRejected**: Capture or policy rejects the pending result; a typed safe
  failure becomes terminal.
- **AssistedRecoveryCommitted**: A pending sanitized incident draft is eligible for recording only
  after `AuthenticatedSessionCommitted`.
- **AdministrativeCancellationWon**: Purge/revocation or shutdown cancels an in-flight finalization.

## Domain Services

- **RemoteAuthenticationManager**: Owns finalization admission, cancellation-source precedence,
  encrypted capture, terminal state, notification ordering, and post-commit incident publication.
- **RemoteBrowserRunner**: Produces code verification, asks the aggregate to begin finalization,
  serializes cookies, closes browser resources, and returns pending sanitized evidence.
- **UserSessionService**: Validates caller ownership and cookie shape, then commits one encrypted
  per-user session through the existing repository.
- **RemoteAuthViewer**: Observes state only. It disables browser/cancel controls during finalization
  and calls Telegram close only after committed success.

## Repository and Port Interfaces

- **CaptureSession**: `telegram_user_id + cookies_json -> committed session result`; exceptions are
  converted to typed capture rejection without exposing their messages.
- **IncidentSink**: Accepts a sanitized `DomIncidentDraft` after final outcome ordering permits it;
  failures are isolated from the already-committed user session.
- **RemoteBrowserRunner**: Receives ready and begin-finalization callbacks; returns one terminal
  result after resource cleanup.
- **AdministrativeCancel**: Target-scoped operation that retains authority during finalization and
  composes with permanent repository revocation.

## Ubiquitous Language

- **Verified**: Code, not a model alone, proved the registered authenticated-inventory postcondition.
- **Finalizing**: Verification succeeded; browser authority is ending and session persistence is
  pending. Ordinary viewer close is no longer cancellation.
- **Committed success**: Encrypted session persistence completed and terminal `succeeded` is visible.
- **Pending recovered incident**: Sanitized assisted evidence not yet allowed to claim recovery.
- **Viewer cancellation**: User-originated abandonment/cancel before verification.
- **Administrative cancellation**: Purge, revocation, or shutdown with higher authority than viewer
  lifecycle convenience.

## Story Coverage

US-140 is fully represented by the finalizing state, source-aware cancellation precedence,
persistence-before-success invariant, post-commit incident eligibility, success-only Mini App close,
and content-free failure observability.
