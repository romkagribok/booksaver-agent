---
stage: design
bolt: 026-remote-authentication-gateway
created: 2026-07-20T02:45:00Z
---

# Technical Design: Remote Authentication Gateway

## Architecture Pattern

Extend the existing hexagonal daemon with one opt-in inbound adapter and an ephemeral browser-process
adapter. The daemon remains the authority for Telegram admission and encrypted session persistence.
Caddy is a TLS sidecar only; it owns no product state. Xvfb, headed Playwright Chromium, x11vnc, and
websockify are child processes of one bounded login worker and are absent when no attempt is active.

This deliberately accepts the trusted-VPS endpoint boundary for the invite-only MVP. It does not claim
that HTTPS or at-rest encryption can protect credentials from a fully compromised VPS root account.

## Layer Structure

- **Domain** (`domain/remote_auth.py`): attempt state machine, settings/value validation, terminal
  invariants, redacted outcomes.
- **Application** (`application/remote_auth.py`): concurrency lease, attempt exchange, viewer-session
  authorization, capture orchestration, cancellation, shutdown, notification callbacks.
- **Infrastructure / browser** (`infrastructure/remote_auth/browser_runner.py`): Xvfb, Playwright,
  x11vnc, token-gated websockify, navigation policy, positive-auth polling, cleanup.
- **Infrastructure / web** (`infrastructure/remote_auth/gateway.py`): stdlib HTTP server, Mini App
  bootstrap, signed-data exchange, HttpOnly cookie endpoints, safe noVNC static serving.
- **Infrastructure / Telegram** (`infrastructure/telegram/connect_command.py`): `/connect`,
  `connect:start` callback, proactive reconnect notice formatting.
- **Composition** (`cli/commands.py`, `daemon/lifecycle.py`): opt-in runtime construction and watchdog.
- **Deployment** (`Dockerfile`, `docker-compose.yml`, `Caddyfile`): required display/VNC packages,
  internal-only ports, public Caddy 80/443, persistent certificate volumes.

## Domain Contracts

- `RemoteAuthenticationManager.create(telegram_user_id, chat_id) -> AttemptLaunch`
- `RemoteAuthenticationManager.exchange(launch_token, verified_telegram_user_id) -> ViewerGrant`
- `RemoteAuthenticationManager.viewer(session_token) -> ViewerState`
- `RemoteAuthenticationManager.cancel(session_token) -> bool`
- `RemoteAuthenticationManager.stop_all() -> None`
- `TelegramInitDataVerifier.verify(raw, expected_user_id, now) -> TelegramMiniAppIdentity`
- `RemoteBrowserRunner.run(attempt, callbacks, stop_event) -> None`
- Existing `UserSessionService.import_cookies(telegram_user_id, raw_cookie_json)` remains the sole
  normalization/encryption write boundary.

## HTTP Contract

- `GET /connect/{launch-token}`: return bootstrap HTML only; `Referrer-Policy: no-referrer`, strict
  CSP, `Cache-Control: no-store`; never includes VNC capability.
- `POST /api/connect/exchange`: body `{launch_token, init_data}`; verify HMAC/freshness/user/attempt,
  consume launch token, set `booksaver_auth` Secure+HttpOnly+SameSite=Strict cookie, return redacted
  status.
- `GET /api/connect/session`: authenticate viewer cookie; return status and, only while ready, the
  noVNC WebSocket path and per-attempt token. The HttpOnly viewer capability itself is never echoed.
- `POST /api/connect/cancel`: authenticate viewer cookie and idempotently terminate the attempt.
- `GET /novnc/...`: serve only files under the configured noVNC root after safe path resolution.
- `GET /healthz`: liveness only; no attempt/user state.

No endpoint accepts Booking.com usernames, passwords, MFA codes, cookie JSON, arbitrary URLs, file
uploads, or free-form browser actions.

## Telegram Mini App Verification

1. Parse the query-string `initData`, reject duplicates/missing `hash`/`auth_date`/`user`.
2. Build Telegram's sorted newline-delimited data-check string excluding `hash`.
3. Derive `secret_key = HMAC-SHA256(key="WebAppData", data=bot_token)` and compare the expected
   HMAC-SHA256 digest in constant time.
4. Require `auth_date` within the configured maximum age and reject material future skew.
5. Parse `user.id` as an integer and require exact equality with the attempt's Telegram user ID.
6. Consume the launch capability and issue a new random viewer capability stored only as a digest.

## Browser and Display Process Design

1. Acquire the global browser lease before creating an attempt.
2. Create a mode-0700 temporary directory outside the persistent session vault.
3. Start Xvfb on the configured private display.
4. Start passwordless x11vnc bound strictly to loopback; it is unreachable from Caddy or the host.
5. Write a mode-0600 websockify `TokenFile` mapping a 256-bit token to the loopback VNC port.
6. Start websockify on the Compose-internal port with stdout/stderr discarded and no record/log file.
7. Launch headed Chromium through Playwright on that display with Intent 013's mobile context and open
   the real Booking.com sign-in URL.
8. Abort unsupported top-level navigation while allowing subresources; attach the policy to new pages.
9. Poll only local rendered account evidence. Do not call observation, screenshot, trace, or LLM code.
10. On positive evidence, capture `context.cookies()`, normalize/save through Unit 001, and signal success.
11. In `finally`, close Playwright, terminate/kill child processes, unlink token files, remove
    the temp directory, clear capabilities, release the lease, and signal the redacted terminal outcome.

## Configuration

Optional `[remote_auth]` fields:

- `enabled = false`
- `public_url = "https://connect.example.com"` (required and HTTPS when enabled)
- `listen_host = "0.0.0.0"`, `listen_port = 8080`
- `websocket_port = 6080`
- `session_timeout_seconds = 600`
- `telegram_init_max_age_seconds = 300`
- `novnc_root = "/usr/share/novnc"`

Enabling requires Telegram bot mode and `BOOKSAVER_TELEGRAM_BOT_TOKEN`. No new application secret is
introduced; all capabilities come from `secrets.token_urlsafe` and only their digests are retained.

## Proactive Reconnect Design

- Scheduled `AUTH_REQUIRED` results call a user-scoped notifier after check persistence.
- The notifier suppresses repeats per local user for a configured in-memory cooldown and sends a
  `connect:start` callback button, not a pre-started browser.
- Tapping the callback or sending `/connect` creates the attempt and replaces the message with the
  Mini App `web_app` button.
- Successful capture clears the caller's reconnect suppression key.
- `/checknow` keeps its existing explicit completion response and does not emit an additional prompt.

## Deployment Design

- Only Caddy publishes host ports `80:80` and `443:443`.
- Caddy routes `/websockify` to `booksaver:6080` and all other paths to `booksaver:8080`; it does not
  emit access logs containing capabilities.
- Python gateway and websockify ports use Compose `expose`, never `ports`.
- Caddy uses a configured public DNS name and automatic certificate storage volumes.
- Remote auth remains disabled until both config and DNS/TLS are ready.
- The browser stack is on-demand and globally serialized to bound memory on the existing VPS.

## Security Controls and Known Boundary

- HMAC-verified Telegram identity, fresh timestamp, exact caller binding, single-use exchange.
- Secure cookie, no-store, CSP, no-referrer, same-origin JSON API, body limits, method allowlist.
- Token-gated WebSocket; passwordless raw VNC is loopback-only and never routed or published.
- No login telemetry; only attempt ID/status and redacted reason classes may be logged.
- No persistence before positive authentication; existing Fernet repository protects captured state.
- A fully compromised VPS/root can instrument the browser or display and observe input. A future issue
  tracks stronger disposable isolation/device-local alternatives; this MVP is only for trusted users.

## Test Design

- Domain transitions, expiry, single-use exchange, busy lease, idempotent teardown.
- Telegram HMAC vectors, age/future skew, malformed/duplicate fields, cross-user/replay denial.
- HTTP headers, cookies, method/body limits, static traversal rejection, secret-free errors.
- Fake runner capture/failure/timeout/cancel/shutdown and active-user revalidation.
- Telegram command/callback/reconnect cooldown and private admission integration.
- Config validation and disabled-mode regression.
- Browser process command construction/cleanup with subprocess and Playwright fakes.
- Compose/Caddy/Docker static assertions; real VPS phone login remains an explicit operations smoke test.
