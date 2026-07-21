---
stage: model
bolt: 026-remote-authentication-gateway
created: 2026-07-20T02:35:00Z
---

# Domain Model: Remote Authentication Gateway

## Ubiquitous Language

- **Connection attempt**: Short-lived aggregate authorizing one admitted Telegram user to establish one Booking.com session.
- **Launch capability**: Opaque single-use value embedded only in the caller's Telegram Mini App URL.
- **Viewer session**: Short-lived server-side authorization created after Telegram `initData` verification; represented to the browser by an HttpOnly cookie.
- **Remote browser lease**: Exclusive ownership of the one VPS virtual display/browser/VNC stack.
- **Positive authentication evidence**: Rendered Booking.com account markers sufficient to capture state; absence of a sign-in prompt is never enough.
- **Terminal teardown**: Idempotent destruction of every process, token, secret, and temporary file belonging to an attempt.
- **Reconnect epoch**: Deduplication key for one transition into an authentication-required state.

## Entities and Value Objects

- **RemoteAuthAttempt** (aggregate root): attempt ID, caller local user ID, Telegram user/chat IDs,
  launch-token digest, viewer-session digest, VNC/WebSocket capability, created/expires timestamps,
  status, and redacted failure class.
- **RemoteAuthStatus**: `starting`, `ready`, `connected`, `succeeded`, `failed`, `expired`,
  `cancelled`; transitions are monotonic and terminal states are immutable.
- **TelegramMiniAppIdentity**: verified Telegram numeric user ID plus fresh `auth_date`; constructed only
  after HMAC validation.
- **RemoteBrowserLease**: one attempt ID plus cancellation/cleanup handle; only one active lease exists.
- **CapturedBookingSession**: normalized Booking.com cookie state plus observation/expiry metadata; it
  exists only in memory before Unit 001 encrypts it.
- **ReconnectNoticeKey**: owner user ID plus session health/revision (or missing sentinel), used to
  suppress repeated notices.

## Aggregate Invariants

1. An attempt belongs to exactly one admitted active user and their private Telegram chat.
2. Launch-token equality uses digests and constant-time comparison; raw capabilities are never logged or persisted.
3. The launch capability can create at most one viewer session and cannot be replayed by another user.
4. No viewer receives WebSocket/VNC capability until Telegram signature, freshness, caller binding,
   attempt lifetime, and attempt state all validate.
5. Only one remote browser lease is active across the VPS.
6. Captured state is saved only after positive Booking.com authentication and a final active-user lookup.
7. Every terminal transition triggers idempotent teardown, including daemon shutdown.
8. Login observations never enter LLM, trace, screenshot, recording, Telegram, or exception payloads.
9. A reconnect notification carries only health and a fresh `/connect` action; it is deduplicated.
10. The flow never performs booking, cancellation, payment, or reservation actions.

## Domain Services and Ports

- **RemoteAuthenticationManager**: create/reuse attempt, exchange launch capability, inspect viewer
  session, cancel, transition status, and stop all.
- **TelegramInitDataVerifier**: verify signed data, freshness, and expected numeric identity.
- **RemoteBrowserRunner**: acquire lease, launch the display/browser/VNC stack, report readiness,
  capture authenticated cookies, and tear down.
- **AuthenticatedCaptureService**: normalize captured Booking.com state and save through Unit 001's
  user-session service after final admission validation.
- **ReconnectNotifier**: decide whether a transition warrants a user-scoped `/connect` prompt.
- **RemoteAuthGateway**: expose bootstrap, exchange, session status, cancellation, and static noVNC
  assets without becoming a general-purpose application API.

## Domain Events

- **ConnectionAttemptCreated**: caller IDs, attempt ID, expiry.
- **RemoteBrowserReady**: attempt ID only.
- **BookingSessionCaptured**: caller local user ID, new revision ID, redacted cookie count/domains.
- **ConnectionAttemptTerminated**: attempt ID, terminal status, redacted reason.
- **ReconnectRequired**: caller ID plus deduplication key.

## Repository Interfaces

- Existing **UserLookup** and **UserSessionRepository** remain the durable identity/session ports.
- Attempt and viewer state are deliberately in-memory only; restart means expiry and teardown.
- Reconnect deduplication may be in-memory for the first version because daemon restart safely allows
  one additional prompt and stores no secret.

## Story Coverage

- US-089: attempt aggregate and browser lease.
- US-090: Mini App identity, launch exchange, viewer session.
- US-091: remote browser runner and observation prohibition.
- US-092: capture service and terminal teardown.
- US-093: terminal events and reconnect key.
- US-094: gateway/TLS trust boundary.
