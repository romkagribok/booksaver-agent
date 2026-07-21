---
intent: 012-per-user-booking-sessions
created: 2026-07-19T21:23:00Z
completed: 2026-07-20T02:25:00Z
status: complete
---

# Inception Log: Per-User Booking.com Sessions

## Overview

**Type**: Brown-field security and capability enhancement.

## Summary

| Metric | Count |
|--------|-------|
| Functional requirements | 12 |
| Units | 2 |
| Stories | 12 |
| Bolts | 2 |

## Decision Log

| Timestamp | Decision | Rationale | Approved |
|-----------|----------|-----------|----------|
| 2026-07-19T21:23:00Z | Separate authentication from mobile emulation | Session security/lifecycle is independently testable and reusable | User authorized |
| 2026-07-19T21:23:00Z | Use owner-operated CLI/SCP import, not Telegram upload | Bot chats are not an appropriate cookie-secret transport | User authorized |
| 2026-07-19T21:23:00Z | Authenticated checks fail closed | Public fallback would hide eligible Genius savings | User authorized |
| 2026-07-20T02:25:00Z | Make `/connect` remote-browser login the primary intake | Phone users can authenticate themselves without Telegram secrets or operator cookie handling | User authorized |
| 2026-07-20T02:25:00Z | Keep the VPS-root threat boundary explicit | HTTPS and encryption cannot protect input from a fully compromised endpoint | User authorized for trusted invite deployments |

## Ready for Construction

- [x] Revised requirements, context, two units, stories, and Bolts 024/026 defined.
- [x] Intermediate checkpoints pre-authorized by the product owner.
- [ ] Final coordinated Test review and bolt completion approval pending.
