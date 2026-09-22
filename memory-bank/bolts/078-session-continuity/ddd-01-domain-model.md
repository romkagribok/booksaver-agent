---
stage: domain-model
bolt: 078-session-continuity
created: "2026-09-20T20:04:41Z"
status: complete
---

# Session continuity domain

The user approved Intent 025 and its routine construction checkpoints. US-195–197 maintain an
existing admitted caller's session; they introduce no interactive login, password storage,
reservation mutation, model authentication decision, or guaranteed month-long validity.

## Aggregate and values

The caller's encrypted session bundle is the aggregate: immutable owner/revision identity,
cookie bytes, legacy expiry, verified freshness, and durable maintenance state. A reconnect
replaces its revision; disconnect removes it; purge prevents recreation. Each wins against
an in-flight maintenance result. All maintenance timestamps are aware UTC values.

Session verification returns exactly AUTHENTICATED, SIGNED_OUT, INTERACTION_REQUIRED or
RETRY_LATER. Only AUTHENTICATED carries nonempty refreshed cookie bytes and verification time.
The code-owned protected-resource contract supplies that fact, never cookie presence or a model.
Incidental cookie expiration is not proof of sign-out. Expired individual cookies are discarded
before restoration without changing any remaining cookie expiration.

Maintenance state contains next attempt, last attempt, consecutive failures, first failure,
and the revision's notification claim. Success clears failures and schedules the next daily
verification; temporary failure advances 15-minute, 1-hour, 6-hour, then 24-hour backoff.
After 48 hours of unresolved verification, claim one uncertainty notice; do not label sign-out.
Confirmed interactive need claims the same once-per-revision reconnect notice.

## Services and repositories

The coordinator admits at most one caller maintenance operation through its existing browser
gate. It rechecks active admission, shutdown and revision before publishing results. A
verification-only repository path can read legacy ACTIVE snapshots whose aggregate expiry
has passed; ordinary resolution remains unavailable until fresh positive proof. Explicit
reauthentication, missing/corrupt bundles, revocation and purge remain blocked.

An atomic attempt claim persists next-due before browser work so process restart cannot create
a retry burst. Atomic completion merges only the still-current caller/revision/attempt. A
foreground authenticated mobile snapshot may update freshness before desktop inventory use;
desktop-mutated cookies never replace the saved price context.
