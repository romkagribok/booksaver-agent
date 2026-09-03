---
intent: 023-replaceable-agentic-browser-executor
phase: inception
status: complete
created: 2026-08-16T19:18:41Z
updated: 2026-09-03T00:36:00Z
---

# System Context: Replaceable Agentic Browser Executor

## Actors

- **Deployment owner** (Human): Self-hosts BookSaver, configures the Anthropic key, owns operational
  cost and privacy policy, runs the live canary, and controls promotion/rollback.
- **Invited user** (Human): Uses the private Telegram bot, supplies a Booking session through
  `/connect`, and may consent to owner-funded agentic checks.
- **BookSaver scheduler/coordinator** (System): Authorizes and serializes checks under the global
  browser lease and daily limits.
- **BookSaver validation/evaluation** (System): Independently validates untrusted observations,
  selects equivalent refundable all-in offers, persists results, and permits notifications.
- **Local browser executor** (System): Performs bounded perception and read-only navigation in a
  transient browser without domain authority. Browser Use handles every inventory trigger and is
  the default executor for both manual and scheduled price checks; Stagehand remains an explicit
  price rollback.
- **Inventory reconciliation policy** (System): Accepts only validated positive reservation
  observations, derives eligibility, and prevents agentic evidence from marking unseen rows absent.

## External Systems

- **Booking.com**: Authenticated mobile-web pricing and account content over HTTPS; dynamic,
  unversioned presentation surface.
- **Anthropic API**: Sonnet 5 semantic and computer-use inference using the deployment owner's key;
  receives bounded visible page evidence but never session cookies or credentials.
- **Telegram**: Existing invite-only user interaction, `/connect` disclosure, and notifications.
- **Loopback services**: In-process Stagehand and Browser Use runners and any local telemetry sink;
  no content export.

## Trust Boundaries

1. BookSaver domain inputs, authorization, session ownership, and budgets are trusted code-owned
   inputs.
2. Decrypted cookies exist only inside a transient local browser boundary. The transient executor
   reuses the configured version-matched mobile identity that produced and verified the session;
   browser identity is part of session compatibility, not model input.
3. Stagehand actions, Browser Use actions, extraction, and Anthropic outputs are untrusted
   proposals/evidence.
4. The code guard owns every browser mutation and rejects unsafe requests before and after action.
5. Only BookSaver validation/evaluation can create a valid candidate, savings opportunity, or
   notification.

## Data Flows

### Inbound

- Trusted booking property reference, dates, occupancy, expected currency, owner/session binding,
  deadline, action limit, and cost reservation.
- Trusted inventory scopes, authorized account binding, and current-run execution identity.
- Stagehand semantic action proposals and typed extraction.
- Browser Use guarded read-only proposals and typed inventory or price submissions.
- Anthropic computer-use action requests, typed observation submissions, terminal outcomes, and
  usage data.
- Booking.com rendered visible content and server-verified authentication state.

### Outbound

- Guarded read-only browser actions to Booking.com.
- Bounded semantic evidence and escalation screenshots to Anthropic.
- Typed, redacted price observations to BookSaver validation.
- Typed positive reservation observations and traversal coverage to BookSaver inventory validation.
- Redacted metrics/failure codes to local persistence and owner-only operations.
- Existing savings notifications after independent validation.

### Forbidden Flows

- Cookies, credentials, MFA values, clipboard, files, model reasoning, or full page evidence to
  results/logs/persistence.
- Model-selected arbitrary URLs or unguarded browser actions.
- Executor decisions about equivalence, savings, transaction authority, or user identity.
- Executor decisions that inventory is authoritatively complete or that an unseen reservation is
  absent.

## System Context Diagram

```mermaid
flowchart LR
    owner["Deployment owner"] --> control["BookSaver trusted control plane"]
    invitee["Invited user"] --> telegram["Private Telegram bot"]
    telegram --> control
    control --> lease["Owner-bound transient session lease"]
    lease --> executor["Replaceable local browser executor"]
    executor --> browseruse["Browser Use OSS for /bookings and price"]
    executor --> stagehand["Stagehand inventory and explicit price rollback"]
    executor --> booking["Booking.com"]
    executor --> anthropic["Anthropic Sonnet 5"]
    executor --> evidence["Typed redacted observations"]
    evidence --> validation["BookSaver validation and evaluation"]
    executor --> inventory["Typed positive inventory evidence"]
    inventory --> reconcile["BookSaver positive-only reconciliation"]
    validation --> persistence["Local persistence and notifications"]
    reconcile --> persistence
    control -. "legacy rollback" .-> legacy["Existing Playwright price path"]
    legacy --> booking
```

## Lifecycle

1. Coordinator authorizes the user and booking, reserves budget, and selects routing mode.
2. Session service decrypts verified cookies into a fresh local browser owned by a scoped lease.
3. The executor first reaches the requested protected Booking.com capability with the matching
   mobile identity. A code-owned preflight rejects unusable model views and sanitized transport,
   authentication, or challenge failures before paid inference whenever detectable.
4. Browser Use receives only task-specific guarded actions and typed terminal submissions; every
   physical action and resulting destination remains code-authorized.
5. Stagehand remains selectable for future jobs as an explicit rollback but never runs after a
   failed Browser Use operation in the same job.
6. Executor returns typed evidence without domain conclusions or secret material.
7. BookSaver validates facts, evaluates equivalence/savings, reconciles cost, optionally persists
   verified refreshed cookies, records redacted metrics, and destroys the browser profile.

## Price Lifecycle

1. `/checknow` and scheduled work resolve through the same price-executor factory and
   `PriceBrowserExecutor` application service.
2. Owner-canary price routes select Browser Use by default; invited-user routing retains disclosure
   and Browser Use-specific qualification gates.
3. The local Browser Use agent navigates and perceives through guarded human-like actions, then
   submits typed query facts and offers or one closed terminal outcome.
4. BookSaver independently verifies property, dates, occupancy, authentication, currency, all-in
   status, explicit refundability, room equivalence, and savings.
5. An operator-only production replay can execute this exact path against isolated state, wait for
   terminal completion, and suppress notifications and authoritative booking mutations.

## Inventory Lifecycle

1. A disclosed authorized user triggers `/bookings`, post-connect synchronization, `/checknow`, or a
   scheduled slot under the single coordinator gate. `/bookings` selects Browser Use; the other
   inventory triggers select Stagehand.
2. BookSaver issues an account-bound session lease and fixed upcoming, past, and cancelled work
   scopes to the inventory executor.
3. The executor restores the session into BookSaver's configured mobile identity and reaches the
   protected inventory resource. Redirect loops and internal browser error pages are classified
   from content-free transport evidence instead of being treated as Booking.com destinations.
4. The selected local harness proposes bounded read-only perception actions. Browser Use uses a
   deny-oriented generic guard for `/bookings`; Stagehand retains its existing task-specific guard
   for other triggers. BookSaver checks every executed destination.
5. The executor returns positive reservation evidence and redacted traversal metadata. It cannot
   establish authoritative absence or completeness.
6. BookSaver validates stable identities and domain facts, persists accepted current-run positives,
   preserves unseen rows, and permits a price check only for a reservation re-observed in that run.
7. A `/bookings` Browser Use failure closes that operation without a same-job Stagehand or legacy
   retry; saved last-safe inventory remains visible.
