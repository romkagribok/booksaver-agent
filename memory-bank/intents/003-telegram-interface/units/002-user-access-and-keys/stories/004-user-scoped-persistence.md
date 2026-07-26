---
id: 004-user-scoped-persistence
status: complete
implemented: true
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

**Implementation note (bolt 009, 2026-07-11):** the schema v7 migration, `users` table,
`UserRepository`, booking/savings repository scoping, owner-resolved CLI wiring, and the
`LLMClientFactory` seam are implemented and tested (see
`memory-bank/bolts/009-user-access-and-keys/`). The per-user bookings cap (config-driven,
default 3) requires config-section changes owned by the parallel Telegram-gateway bolt
(config loading is out of this slice's touched-files scope) and is **not yet enforced** —
tracked as a follow-up for whichever bolt next touches `[access]`/registration config
(bolt 010 conversational-booking-ops is the natural home, since it owns the registration
dialog).

---
