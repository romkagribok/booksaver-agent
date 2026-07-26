---
unit: 001-remote-auth-display-reliability
intent: 014-remote-auth-display-reliability
phase: inception
status: complete
unit_type: cli
default_bolt_type: simple-construction-bolt
created: 2026-07-26T17:55:43.000Z
updated: 2026-07-26T17:55:43.000Z
---

# Unit Brief: Remote Authentication Display Reliability

## Purpose

Make the existing Telegram `/connect` viewer render the live mobile Chromium framebuffer and report
viewer failures without relaxing identity, origin, network, or cleanup boundaries.

## Scope

### In Scope

- CSP policy emitted by `RemoteAuthHttpApp._bootstrap`.
- noVNC RFB event handling in the generated Mini App JavaScript.
- Unit-level security and behavior regression coverage.

### Out of Scope

- Remote-auth manager/session lifecycle, Telegram signature verification, Caddy topology, and
  Booking.com login detection.
- Native application automation or public VNC access.

## Assigned Requirements

| FR | Requirement | Priority |
|----|-------------|----------|
| FR-1 | Render noVNC framebuffer image updates | Must |
| FR-2 | Explain noVNC connection failures | Must |

## Story Summary

| Story ID | Title | Priority | Status |
|----------|-------|----------|--------|
| US-095 | Render the remote mobile-browser framebuffer | Must | Ready |
| US-096 | Explain remote viewer connection failures | Must | Ready |

## Dependencies

- Completed Bolt 026 remote-authentication gateway.
- Packaged noVNC `Display.imageRect()` behavior and same-origin WebSocket route.

## Constraints

- Permit only `data:` images; keep third-party images and all default resources blocked.
- Never expose tokens, cookies, capability paths, or Booking.com content in error messages/logs.
- Preserve cancellation, expiry, and single-browser cleanup.

## Success Criteria

- [ ] CSP regression test proves `img-src data:` and rejects broad image sources.
- [ ] Viewer event regression tests prove safe security/disconnect feedback.
- [ ] Targeted and full quality gates pass.
- [ ] Human review approves the fix before commit/push/deployment.

## Bolt Suggestions

| Bolt | Type | Stories | Objective |
|------|------|---------|-----------|
| 027-remote-auth-display-reliability | Simple | US-095, US-096 | Correct and verify the Mini App viewer |
