---
id: 006-deploy-gateway-behind-https
unit: 002-remote-authentication-gateway
intent: 012-per-user-booking-sessions
status: complete
priority: must
created: 2026-07-20T02:25:00.000Z
assigned_bolt: 026-remote-authentication-gateway
implemented: true
---
# Story: Deploy the Gateway Behind HTTPS
**Global story ID**: US-094

As the VPS operator, I want a narrow opt-in HTTPS boundary so that phone authentication is reachable without publishing the daemon or VNC directly.

## Acceptance Criteria
- [ ] Caddy alone publishes ports 80/443; gateway and websockify remain Compose-internal.
- [ ] Public URL, DNS, firewall, memory, smoke test, revocation, and shutdown are documented.
- [ ] Disabled/unconfigured remote auth preserves existing laptop and daemon operation.
