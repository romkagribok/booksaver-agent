---
id: US-029
status: ready
implemented: false
---

# US-029 User-scoped persistence (schema v7)

**Intent:** `003-telegram-interface`
**Unit:** `002-user-access-and-keys`
**Status:** Ready
**Tag:** Phase 3

## Story

**As a** user of a shared bot
**I want** my bookings, checks, savings, and rebook history tied to my identity
**So that** no other user can see or affect my data

**Acceptance criteria**

- Schema v7 adds a `users` table (telegram user ID, access state, encrypted key blob, created_at) and `user_id` on bookings; checks/savings/rebook sessions/traces inherit scope through the booking
- Migration assigns all pre-v7 rows to the owner user; a laptop deployment (one user) behaves identically after migration
- Repository APIs require a user scope; cross-user reads are impossible by construction (integration tests prove isolation)
- CLI commands operate as the owner user
- Per-user bookings cap (config, default 3) enforced at registration

---
