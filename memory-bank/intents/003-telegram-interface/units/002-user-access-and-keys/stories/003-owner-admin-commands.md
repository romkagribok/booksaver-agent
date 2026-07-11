---
id: US-028
status: ready
implemented: false
---

# US-028 Owner admin commands

**Intent:** `003-telegram-interface`
**Unit:** `002-user-access-and-keys`
**Status:** Ready
**Tag:** Phase 3

## Story

**As the** bot owner
**I want** admin commands to manage users from chat
**So that** I can share and revoke access without SSH

**Acceptance criteria**

- `/admin users` lists users (ID, access state, key present yes/no, bookings count) — owner only
- `/admin revoke <user>` disables a user: their checks stop, their data is retained (or purged with `/admin purge <user>` after confirmation)
- `/admin invite` issues a single-use invite code (invite mode)
- `/admin mode <owner|invite>` switches access mode at runtime with confirmation
- Admin commands are refused for non-owner users regardless of mode, with an audit log entry

---
