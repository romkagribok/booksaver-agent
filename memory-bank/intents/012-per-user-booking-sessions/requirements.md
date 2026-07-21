---
intent: 012-per-user-booking-sessions
phase: inception
status: complete
created: 2026-07-19T21:23:00.000Z
updated: 2026-07-20T02:25:00.000Z
---

# Requirements: Per-User Booking.com Sessions

## Intent Overview

Make authenticated Booking.com pricing a trustworthy per-user capability. Every Telegram user's
checks must use only that user's encrypted, current Booking.com browser session so Genius and other
logged-in prices can be observed without leaking the owner's account or silently degrading to public
rates.

## Business Goals

| Goal | Success Metric | Priority |
|------|----------------|----------|
| Observe account-eligible prices | Authenticated checks can render logged-in/Genius offers | Must |
| Preserve multi-user isolation | No check can load another user's browser state | Must |
| Fail honestly | Missing, expired, corrupt, or signed-out state never becomes a public-price result | Must |
| Remove operator-mediated onboarding | Invited users can establish or refresh their own session from Telegram | Must |

## Functional Requirements

### FR-1: Isolate Booking.com sessions by user
- **Description**: Bind one Booking.com session aggregate to the stable local user ID and create a clean browser context before restoring it.
- **Acceptance Criteria**:
  - A booking check resolves its owner and only that owner's session.
  - Owner/global/foreign cookies are never a fallback for an invited user.
  - A clean context or equivalent proven barrier prevents cookie/local-storage bleed between users.
- **Priority**: Must
- **Related Stories**: US-077

### FR-2: Retain a secure operator recovery import
- **Description**: Retain CLI cookie import/status operations with an explicit admitted Telegram user target as an emergency recovery path; cookie payloads never travel through Telegram.
- **Acceptance Criteria**:
  - Import rejects an unknown/revoked target, malformed/expired/non-Booking.com cookies, and ambiguous target selection before persistence.
  - Output contains counts/domains/health only, never cookie values.
  - The operator is instructed to use SCP/SSH and delete the source export after import.
- **Priority**: Must
- **Related Stories**: US-078

### FR-3: Protect browser state at rest
- **Description**: Encrypt each user's normalized Playwright-restorable state using the existing Fernet secret pattern and write it atomically with restrictive permissions.
- **Acceptance Criteria**:
  - Raw cookies/storage state are never stored as plaintext/base64-only or in SQLite/logs/traces.
  - Wrong/missing encryption key fails closed without destroying the stored bundle.
  - Legacy global owner state is migrated only through an explicit, tested owner mapping; it is never implicitly shared.
- **Priority**: Must
- **Related Stories**: US-079

### FR-4: Inspect session health without disclosing secrets
- **Description**: Provide CLI and user-scoped Telegram status information for missing, ready, expired, reauthentication-required, or invalid sessions.
- **Acceptance Criteria**:
  - A user sees only their own state; owner aggregate views reveal no cookies or another user's account details.
  - Status includes last validation/expiry and an actionable re-import command using Telegram ID.
- **Priority**: Must
- **Related Stories**: US-080

### FR-5: Enforce authenticated-only check policy
- **Description**: Telegram-owned scheduled and on-demand checks require a valid authenticated session and may not fall back to public or another user's pricing.
- **Acceptance Criteria**:
  - Missing/expired/corrupt/signed-out/ambiguous state produces a typed `auth_required` or inconclusive failure scoped to that user.
  - Other users' checks continue, quotas/history remain consistent, and no savings alert is emitted from degraded context.
  - Session revision is revalidated when refreshed/invalidated to avoid overwriting a newer import.
- **Priority**: Must
- **Related Stories**: US-081

### FR-6: Preserve lifecycle and human-action safety
- **Description**: Refresh valid state after checks, support deletion/replacement, honor revocation, and preserve the device-side final booking boundary.
- **Acceptance Criteria**:
  - Revocation prevents resolution and refresh; deletion removes only that user's encrypted session.
  - Refreshed cookies update the same revision only when still current.
  - Session support never enables autonomous cancel, reserve, checkout, or payment actions.
- **Priority**: Must
- **Related Stories**: US-082

### FR-7: Start a user-bound connection from Telegram
- **Description**: Let an admitted user request a short-lived Booking.com connection attempt with `/connect` and open it through a Telegram Mini App button.
- **Acceptance Criteria**:
  - The command works only in the existing private-chat admission boundary and targets the caller.
  - Attempts use cryptographically random opaque identifiers, expire within a configured bound, and are single-use for browser admission.
  - At most one remote login browser is active on the small self-hosted VPS; competing attempts receive a clear busy response.
- **Priority**: Must
- **Related Stories**: US-089

### FR-8: Verify Telegram identity before exposing the browser
- **Description**: Validate Telegram Mini App `initData` at the HTTPS gateway and bind it to the attempt's initiating numeric Telegram user ID.
- **Acceptance Criteria**:
  - HMAC validation, `auth_date` freshness, expected user ID, attempt state, and expiry all pass before VNC credentials are returned.
  - Invalid, stale, replayed, forwarded, or cross-user requests fail without revealing attempt or browser details.
  - Successful exchange replaces the URL capability with a short-lived Secure, HttpOnly, SameSite cookie.
- **Priority**: Must
- **Related Stories**: US-090

### FR-9: Run an interactive mobile browser on the VPS
- **Description**: Start a fresh headed Chromium mobile-web context on an isolated virtual display and expose only that display through noVNC/websockify behind HTTPS.
- **Acceptance Criteria**:
  - The login page is the real Booking.com origin rendered by VPS Chromium; BookSaver never renders or submits a password form.
  - The browser uses the same allowlisted mobile profile policy as authenticated checks.
  - No login screenshot, video, trace, LLM observation, clipboard UI, or websockify recording is enabled.
  - Top-level navigation is restricted to Booking.com and explicitly supported identity-provider origins.
- **Priority**: Must
- **Related Stories**: US-091

### FR-10: Capture authenticated state and tear down
- **Description**: Detect positive rendered authentication, normalize the context's Booking.com cookies through the existing import boundary, encrypt them for the caller, and destroy all transient login resources.
- **Acceptance Criteria**:
  - State is persisted only after positive authenticated evidence and a final active-user check.
  - Successful capture atomically replaces only the caller's encrypted session revision.
  - Success, cancellation, timeout, revocation, browser crash, and daemon shutdown all terminate Chromium, VNC, websockify, the virtual display, token files, and in-memory access credentials.
- **Priority**: Must
- **Related Stories**: US-092

### FR-11: Give visible outcomes and reconnect guidance
- **Description**: Tell the caller whether connection succeeded, failed, timed out, or was cancelled, and provide a deduplicated reconnect action when a scheduled check first discovers an unusable session.
- **Acceptance Criteria**:
  - `/connect` returns immediately with an opening message/button while setup continues in the background.
  - Completion is proactively delivered in Telegram without exposing cookies, account identifiers, passwords, or infrastructure details.
  - Reconnect notification is emitted once per user/session-health transition or cooldown, not on every scheduled booking failure.
- **Priority**: Must
- **Related Stories**: US-093

### FR-12: Expose the gateway safely on a self-hosted VPS
- **Description**: Add an opt-in inbound HTTPS deployment boundary without turning BookSaver into a public service.
- **Acceptance Criteria**:
  - Caddy is the only public listener, automatically terminates TLS, and proxies the gateway and WebSocket internally.
  - The Python gateway and VNC ports are not published to the host; auth access logging is disabled or secret-redacted.
  - The feature is disabled unless an HTTPS public URL is configured; laptop/headless-check operation remains compatible.
  - The runbook documents DNS, firewall, memory, shutdown, smoke-test, and incident/revocation procedures.
- **Priority**: Must
- **Related Stories**: US-094

## Non-Functional Requirements

### Security and Privacy
- Cross-user session-isolation tests must cover owner/invitee, revocation, stale revisions, and repeated sequential checks.
- Secrets must be redacted from exceptions, logs, traces, CLI output, Telegram output, and test failure snapshots.
- The gateway must validate Telegram-signed identity and use at least 128 bits of entropy for transient capabilities.
- HTTPS protects transit but does not claim protection from a fully compromised owner-operated VPS; this trust boundary must be disclosed.

### Reliability
- Import/replacement is atomic; an existing valid encrypted bundle survives rejected input or key errors.
- One user's authentication failure cannot stop the daemon or another user's check.
- Remote-login setup must not block Telegram polling or scheduled check shutdown.

### Compatibility and Verification
- Reuse `cryptography`, Playwright sync API, the existing serialized check coordinator, and SQLite user identity.
- Full pytest, Ruff, mypy, diff, and AI-DLC artifact validation must pass.

## Constraints

- Self-hosted owner-operated laptop/VPS only; no BookSaver-hosted credential backend.
- No Telegram cookie/password upload. Credentials are typed into the real Booking.com page in the remote browser and are never intentionally inspected or persisted by BookSaver.
- Booking.com hotel checks remain refundable/equivalent-only; final purchase remains on the user's device.

## Assumptions and Decisions

- The primary session intake is `/connect`; the operator CLI import remains break-glass recovery.
- Authentication can expire independently of cookie expiry; rendered sign-in state remains authoritative.
- This intent amends ADR-010's one-global-file/base64-only design.
- The product owner approved the HTTPS remote-browser design and authorized inception and all DDD stages through Test; formal bolt completion, commit, push, and deployment are held for final review.

## Scope Exclusions

- Native Booking.com app automation, password/MFA automation, Telegram document upload, a BookSaver-hosted session exchange, and protection against a fully compromised VPS root account.
