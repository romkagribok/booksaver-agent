---
stage: test
bolt: 026-remote-authentication-gateway
created: 2026-07-20T02:55:21Z
---

# Test Report: Remote Authentication Gateway

## Result

Local implementation and regression verification passed. Bolt 026 remains `in-progress` at the
human review gate; its stories are not marked implemented and no commit, push, deployment, or formal
bolt completion has occurred.

## Automated Evidence

| Verification | Result |
|--------------|--------|
| Full Python suite: `python3 -m pytest` | 867 passed |
| Ruff: `python3 -m ruff check src/ tests/` | Clean |
| mypy: `python3 -m mypy src/` | Clean across 93 source files |
| Patch hygiene: `git diff --check` | Clean |
| Compose interpolation/profile: `docker compose --profile remote-auth config --quiet` with non-secret test environment | Valid |
| Remote-auth focused tests | 26 passed inside full suite |

The focused coverage includes settings/origin validation; attempt ownership, one-use exchange,
expiry, cancellation/capture atomicity, browser-lease exclusion, redacted capture failure, and
terminal cleanup; Telegram Mini App HMAC, time skew, duplicate fields, tampering, cross-user denial,
and replay denial; exact-origin API protection, Secure/HttpOnly/SameSite cookie issuance, CSP,
no-store/no-referrer headers, viewer-cookie scoping, static traversal rejection; Booking.com and
explicit identity-provider top-level navigation allowlisting, download cancellation; `/connect`
and reconnect callback UX; per-user reconnect cooldown; lifecycle service watchdog; config gating;
and Docker/Caddy internal-port/static topology.

## Acceptance Evidence

| Story | Evidence | Result |
|-------|----------|--------|
| US-089 | Caller-bound `/connect`, opaque capabilities, one global browser lease, disabled/busy handling | Pass locally |
| US-090 | Signed/fresh/exact Telegram identity, replay cache, single-use exchange, hardened viewer cookie | Pass locally |
| US-091 | Fresh headed mobile context, Xvfb/x11vnc/websockify process design, allowlisted navigation, downloads/recordings/LLM absent | Pass by unit/static inspection; real display pending |
| US-092 | Positive account evidence, active-user revalidation in the existing import boundary, encrypted scoped save, atomic cancel-vs-capture, process `finally` teardown | Pass locally |
| US-093 | Redacted terminal Telegram outcomes, scheduled user-scoped reconnect callback, cooldown and success reset | Pass locally |
| US-094 | Opt-in HTTPS config, Caddy-only host publication, internal gateway/proxy ports, runbook and disabled-mode regression | Pass local config/static checks; VPS pending |

## Security Review Findings Addressed During Test

- Fixed a cancellation race that could otherwise persist cookies after the attempt had been marked
  cancelled. Capture plus the success transition is now atomic with cancellation.
- Added an in-memory replay cache for already accepted signed Telegram `initData`.
- Tightened `public_url` to an HTTPS origin only; paths, credentials, query, and fragments are refused.
- Moved navigation routing to the browser-context level so popups inherit the allowlist and the
  initial page does not receive duplicate handlers.
- Made raw x11vnc explicitly loopback-only on fixed port 5900; only the token-gated websockify route
  is reachable through Caddy.
- Removed conflicting static cache headers; every authentication response remains `no-store`.
- Terminal viewer capability indexes are pruned at attempt expiry so completed links do not remain
  valid for status polling for the daemon lifetime.

## Required Operations Gates

These cannot be proven on this Mac-only review environment and must be run before relying on the
feature in production:

1. **Docker image build:** attempted locally but Docker Desktop was not running
   (`Cannot connect to the Docker daemon`). The Compose model itself validates. Build on the VPS or
   with Docker running to prove Debian package availability and image assembly.
2. **Real phone/VPS login:** configure DNS/TLS, start the `remote-auth` profile, open `/connect` in a
   private Telegram chat, complete Booking.com authentication/MFA, confirm encrypted status, then run
   `/checknow` and inspect authenticated-mobile/Genius provenance.
3. **Cleanup observation:** during the smoke test, confirm Xvfb/x11vnc/websockify/headed Chromium exist
   only while the attempt is active and vanish on success, cancel, timeout, and container shutdown.
4. **Firewall:** verify host ports 8080, 5900, and 6080 are unreachable externally and only SSH,
   HTTP, and HTTPS are published as intended.

## Known Boundary and Follow-up

The approved MVP trusts the self-hosted VPS execution host. Root compromise can still instrument the
remote browser/display and observe login input. [GitHub issue #6](https://github.com/roman-marchuk/booksaver-agent/issues/6)
tracks disposable/microVM isolation and practical device-local alternatives before broader or
untrusted-user deployment.

The AI-DLC artifact validator still reports 38 historical errors in pre-existing intents/bolts
(legacy story-ID/filename conventions and Bolt 009 references). It reports no errors against the new
Intent 012 Unit 002 or Bolt 026 artifacts. No automated fixer was run because that would rewrite
unrelated historical work.
