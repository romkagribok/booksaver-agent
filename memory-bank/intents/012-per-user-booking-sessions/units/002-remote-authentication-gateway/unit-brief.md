---
unit: 002-remote-authentication-gateway
intent: 012-per-user-booking-sessions
phase: construction
status: complete
unit_type: backend
default_bolt_type: ddd-construction-bolt
created: 2026-07-20T02:25:00.000Z
updated: 2026-07-20T02:25:00.000Z
---

# Unit Brief: Remote Authentication Gateway

## Purpose

Let an admitted Telegram user establish or refresh their own encrypted Booking.com session from a
phone without sending a password, MFA code, or cookie export through Telegram or involving the VPS
operator in ordinary onboarding.

## Scope and Operations

- `/connect` creates one short-lived, caller-bound attempt and Telegram Mini App button.
- HTTPS gateway verifies signed Telegram `initData`, freshness, attempt ownership, and replay state.
- One transient headed mobile Chromium is streamed through noVNC/websockify.
- Positive Booking.com authentication is captured into Unit 001's encrypted per-user repository.
- All processes/tokens are destroyed on every terminal path and the user receives a redacted result.
- Caddy owns public TLS; raw gateway, VNC, and WebSocket listeners remain internal.
- Scheduled `auth_required` outcomes produce bounded, deduplicated reconnect guidance.

## Assigned Requirements

FR-7, FR-8, FR-9, FR-10, FR-11, and FR-12.

## Story Summary

| Story | Title | Priority | Status |
|-------|-------|----------|--------|
| US-089 | Request a user-bound login | Must | Ready |
| US-090 | Verify Mini App identity and prevent replay | Must | Ready |
| US-091 | Operate a transient remote mobile browser | Must | Ready |
| US-092 | Capture authenticated state and tear down | Must | Ready |
| US-093 | Report outcomes and request reconnect | Must | Ready |
| US-094 | Deploy the gateway behind HTTPS | Must | Ready |

## Dependencies

- Bolt 024 encrypted per-user session repository and import normalization.
- Existing Telegram private-chat admission and numeric identity.
- Intent 013 mobile profile and positive authentication evidence.

## Success Criteria

- A real admitted user can complete Booking.com login from a phone and receive a ready encrypted session.
- Forwarded/stale/cross-user links reveal no browser capability.
- No credential-bearing login observations enter Telegram, traces, screenshots, LLMs, or logs.
- Timeout, failure, cancellation, shutdown, and success all leave no live transient browser stack.
- Existing laptop and disabled-feature operation remain regression-safe.
