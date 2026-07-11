---
unit: 005-vps-deployment
bolt: 012-vps-deployment
stage: model
status: complete
updated: 2026-07-11T17:45:00Z
---

# Domain Model — VPS Deployment (slice 1: US-034 + logged-out core of US-035)

> Scope: **US-034** (deploy on a VPS) and the **logged-out-checks** half of **US-035**. Cookie
> import (the other half of US-035) is out of scope for this slice — its domain model (imported
> cookie state, expiry, re-import prompts) is deferred to the next bolt slice. No source code in
> this stage description; see `ddd-02-technical-design.md` for the module map.

## Bounded Context

**Deployment & Session Mode** sits at the seam between the existing Search Journey context (bolt
006/007) and the operational environment. It owns one new concept:

1. **Session mode** — an explicit, first-class answer to "does this check have a Booking.com
   session to restore?" A display-less VPS structurally cannot run headed `booksaver auth`, so
   "no session" must be a normal operating mode with its own (already-existing) failure
   vocabulary, not a permanent blocking error.

The Dockerfile/systemd/runbook artifacts themselves are operational, not domain, concerns and are
described in the technical design stage.

## Value Objects

| Value Object | Properties | Constraints |
|--------------|------------|-------------|
| **SessionMode** (new, `domain/session.py`) | enum: `LOGGED_OUT`, `AUTHENTICATED` | `AUTHENTICATED` iff a session was loaded, is not `REQUIRES_REAUTH`, and is not expired at evaluation time; every other case (no session, expired, flagged) is `LOGGED_OUT` — there is no third "broken" state a scheduled check needs to distinguish |

## Domain Rules

### Session mode determination (US-035 logged-out core)
1. `SessionManager.current_mode()` reports the mode a check *would* run in, without mutating
   stored session state — a read-only accessor safe to poll from a future `/status` command,
   unlike `ensure_active()` (which persists an `EXPIRED` transition as a side effect).
2. `SessionManager.ensure_active()` is unchanged in its own contract (returns `None` for
   missing/expired/reauth-required sessions, still transitions expired sessions to `EXPIRED`).
   What changes is the *caller's* reaction: `BookingComSearchMonitor.run_all_active()` no longer
   treats `ensure_active() is None` as a blocking failure for every booking — it proceeds in
   `SessionMode.LOGGED_OUT` instead.
3. In `LOGGED_OUT` mode, no cookies are restored before the journey runs, and no cookie-refresh
   save happens afterwards (there is nothing to refresh).
4. `AUTH_REQUIRED` is redefined, in practice, as "a previously-usable session dropped mid-journey"
   — it presupposes a session existed. `SearchJourney`'s failure classifier
   (`_classify_failure`) is threaded a `SessionMode` and only ever returns `AUTH_REQUIRED` when
   that mode is `AUTHENTICATED`; in `LOGGED_OUT` mode a "sign in to continue" banner on the page
   is expected background noise (Booking.com shows it to anonymous visitors too) and falls
   through to the ordinary step-specific failure code instead. `BOT_WALL` classification is
   unaffected by session mode — a captcha/interstitial is a wall either way.
5. A successful check made in `LOGGED_OUT` mode is a real, bookable public total — not a degraded
   or estimated price — but it may be missing member/Genius rates a signed-in check would surface.
   This is **logged**, not persisted as a new field (schema is owned by another in-flight worker
   this bolt cannot touch); a future slice's cookie-import path is the intended way to see
   member rates instead of adding a schema field just to mark "this price might not be the best
   one available."

## New Failure Codes

None. This slice deliberately reuses the existing `FailureCode` vocabulary (`STEP_FAILED`,
`BOT_WALL`, `PROPERTY_NOT_FOUND`, etc. from bolts 006/007) — it *narrows* when `AUTH_REQUIRED` can
be produced rather than adding a code, keeping the failure-code surface (and any downstream
consumer, e.g. Telegram alert formatting) unchanged.

## Domain Services

| Service | Operations | Dependencies |
|---------|------------|--------------|
| **SessionManager** | + `current_mode() -> SessionMode` (new, read-only) | `SessionRepository` port (unchanged) |
| **SearchJourney** | constructor + `session_mode: SessionMode = AUTHENTICATED` (new, defaulted for backward compatibility with existing direct callers/tests); `_classify_failure` consults it | unchanged otherwise |
| **BookingComSearchMonitor** | `run_all_active()` computes mode from `ensure_active()`'s result instead of failing on `None`; `run_check(booking, session_mode=AUTHENTICATED)` threads it through to the journey | unchanged ports |

## Port Changes

None. No new ports; `InteractiveBrowser`, `SessionRepository`, and friends are untouched. This
slice is pure domain/application-layer logic plus deployment artifacts, which is why it could
proceed without touching the SQLite schema/repository files owned by another in-flight worker.

## Persistence Impact

None. `SessionMode` is not persisted — it is recomputed per check from existing `SessionState`
data already in `session_booking_com.json` (ADR-010). No schema migration.
