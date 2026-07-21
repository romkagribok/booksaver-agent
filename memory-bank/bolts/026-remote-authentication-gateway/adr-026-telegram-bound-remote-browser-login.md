---
adr: ADR-026
status: accepted
created: 2026-07-20T02:45:00Z
bolt: 026-remote-authentication-gateway
amends: ADR-018, ADR-024
---

# ADR-026: Telegram-Bound HTTPS Remote Browser Login

## Context

ADR-024 made authenticated state encrypted and user-isolated but selected operator-side cookie export
and SCP/SSH as its ordinary intake. That is unacceptable for phone-first invited users. A normal link
opening Booking.com on the phone cannot transfer Booking.com's origin-scoped cookies to the VPS, and
Telegram bot messages are not a credential transport.

The product is self-hosted and invite-only. Users trust the owner-operated VPS enough to let it run
their authenticated price checks, but the design must remain honest that a compromised VPS endpoint
could observe interactive login input.

## Decision

Make `/connect` the primary session intake. It opens a Telegram Mini App over HTTPS, validates signed
Telegram `initData`, and grants short-lived access to one headed mobile Chromium running on the VPS.
The phone controls that display using noVNC/websockify. Playwright observes only positive account
evidence, captures Booking.com cookies into ADR-024's encrypted per-user vault, and tears down all
transient processes and capabilities.

Caddy is the sole public TLS boundary. The Python gateway, websockify, and VNC listeners are internal
or loopback-only. CLI import remains a documented break-glass recovery path. The feature is opt-in and
does not convert BookSaver into a public bot or hosted credential service.

## Alternatives Considered

1. **Send account/password through Telegram**: rejected; Telegram bot messages are not a suitable
   secret channel and the VPS would need reversible credentials.
2. **Open Booking.com locally and copy cookies automatically**: impossible without Booking.com OAuth
   or a local companion because browser origin isolation prevents BookSaver reading those cookies.
3. **Browser extension/local companion**: stronger endpoint boundary but rejected for current phone-first UX.
4. **Reverse-proxy Booking.com through BookSaver**: rejected as fragile, credential-handling, and unsafe
   across CSP, cookies, scripts, and anti-abuse behavior.
5. **Custom CDP/WebRTC remote browser protocol**: rejected for the MVP because it creates a large,
   security-sensitive input/streaming surface; noVNC is mature and mobile-capable.
6. **Third-party hosted remote browser**: rejected because it adds another credential/session processor
   and violates the self-hosted trust model.

## Consequences

- Invited users can authenticate and reconnect from a phone without operator cookie handling.
- BookSaver gains its first inbound HTTPS/WSS surface, Caddy dependency, DNS/firewall setup, and an
  on-demand headed browser/VNC process stack.
- The VPS must have enough transient memory and Booking.com must accept its datacenter IP.
- Password-manager autofill and passkeys may be awkward through a remote canvas; MFA remains interactive.
- HTTPS protects transit and Fernet protects captured state at rest, but neither protects input from a
  fully compromised VPS root account. This is acceptable only for the current trusted invite model.
- [GitHub issue #6](https://github.com/roman-marchuk/booksaver-agent/issues/6) tracks stronger
  disposable isolation and device-local alternatives before any broader/untrusted-user deployment.
- Native Booking.com app-only prices remain outside scope; the captured session powers authenticated
  mobile-web checks under ADR-025.
