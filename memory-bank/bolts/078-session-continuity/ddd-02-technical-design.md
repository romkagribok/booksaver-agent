---
stage: design
bolt: 078-session-continuity
created: "2026-09-20T20:09:00Z"
status: complete
---

# Technical design

Retain the existing coordinator execution gate, Playwright/Chromium mobile profile and atomic
encrypted per-user repository. The Linux daemon supervises one ephemeral verification worker
under that same gate; this is a cleanup boundary, not a second browser service or scheduler.
No database schema, new dependency, endpoint, model call or arbitrary URL input is required.

## Contracts

`domain.session_maintenance` owns `SessionVerificationOutcome` and frozen
`SessionVerificationResult(outcome, cookies, verified_at)`, plus the maintenance-run result.
`BrowserSessionMaintenance.verify(cookies, deadline)` is a synchronous boundary suitable for
the coordinator scheduler thread: at most 60 seconds including browser startup/close, at most
two complete verification attempts, redirects disabled and no nested transport retries. Each
attempt uses one cookie-free negative baseline and two independent positive contexts with the
exact same candidate snapshot: at most six fixed protected-account GETs overall. The first
verified context can supply rotated cookies; if changed, the second full attempt must verify
that exact candidate before persistence. Later rotations cannot replace the verified candidate.
Challenges, 429/5xx, timeout, 202 pending and unrecognized responses remain retryable. A qualified
Booking OAuth redirect for the stored candidate can prove sign-out.
No model/page chooses an endpoint or authentication predicate. Cookie bytes never enter logs.

The host's foreground verification additionally retains its established bounded navigation
settling, but uses the same typed server classification. Its initial positive mobile snapshot
can be carried by safe OBSERVED inventory/price results. Grouped traversal retains the snapshot
captured before any desktop preference; it never exports its final desktop context. Other
terminal result contracts remain unchanged; dedicated maintenance handles those cases.

`CheckCoordinator.request_session_maintenance(user_id, now=None)` admits one exact caller and
returns a typed bounded run result. `run_session_maintenance()` is a scheduler wake handler:
find due admitted users regardless of bookings, attempt one through the shared gate, return
the next requested UTC wake. Busy/shutdown admissions do not claim an attempt. The production
CLI registers this handler alongside randomized reservation checks.

## Process ownership and cleanup

The hard 60-second deadline includes launch, probes and confirmed cleanup. The ephemeral Linux
worker enables child-subreaper ownership before it receives private cookie material over a
bounded inherited socket. Cookies never enter argv, files or logs. The parent freezes its exact
process tree, follows detached descendants through `/proc`, verifies PID start times before
signaling, and confirms owned processes have exited before returning. No broad process kill is
allowed. Unconfirmed cleanup raises a distinct fatal ownership error: the coordinator sets its
shared stop event before releasing the gate, prohibiting further browser admission and requiring
lifecycle/container cleanup. Unsupported platforms disable background maintenance with one
operator diagnostic, without recording retry failures or creating 48-hour reconnect notices.
Normal foreground and interactive login paths retain their existing platform support.

## Durable state and migration

Add explicit continuity policy version and maintenance timestamps/counters to the encrypted
payload; absent fields mean legacy policy. Keep existing envelope compatibility and owner
binding. New imports no longer treat aggregate cookie expiry as authentication lifetime.
Legacy ACTIVE local-expired snapshots remain blocked in ordinary resolve but may be loaded
only for maintenance. Fresh positive proof clears obsolete aggregate expiry and stamps the
new policy/freshness. Explicit EXPIRED/REQUIRES_REAUTH, corrupt, missing and purged snapshots
are not recovered automatically. UTC-aware validation rejects malformed metadata.

Claim attempts and complete results under the existing per-owner lock using revision and
attempt timestamp checks. Persist the next backoff before opening a browser. A fresh login,
disconnect or purge defeats stale completion. Active user access is checked around browser
work and during completion; no owner fallback is available.

## Notifications and verification

Success and temporary failures are silent. Store the once-per-revision notice claim before
delivery to avoid restart duplication. Confirmed sign-out uses the existing reconnect wording;
48-hour uncertainty says the login could not be verified. New login resets the claim.

Tests cover exact outcome/cookie contracts, old/new expiry policies, UTC/corrupt state, durable
claim/backoff, stale revisions/disconnect/purge, inactive caller, no-booking maintenance,
gate contention/shutdown, notification deduplication and uncertainty copy, typed response
classification, expired-cookie filtering and pre-desktop provenance. Root owns whole-suite,
current-head review and exact-image live qualification; mocks are not native Telegram proof.
