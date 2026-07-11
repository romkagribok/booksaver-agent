---
id: 009-user-access-and-keys
unit: 002-user-access-and-keys
intent: 003-telegram-interface
type: ddd-construction-bolt
status: in_progress
stories:
  - 026-enforce-access-modes
  - 027-bring-your-own-anthropic-key
  - 028-owner-admin-commands
  - 029-user-scoped-persistence
created: 2026-07-11T17:39:20Z
started: 2026-07-11T17:39:20Z
completed: null
current_stage: implement
stages_completed:
  - name: model
    completed: 2026-07-11T17:50:00Z
    artifact: ddd-01-domain-model.md
  - name: design
    completed: 2026-07-11T17:52:00Z
    artifact: ddd-02-technical-design.md
  - name: implement (US-029 slice only)
    completed: 2026-07-11T17:57:19Z
    artifact: domain/user.py + schema v7 migration + SqliteUserRepository +
      BookingRepository/SavingsRepository scoping + LLMClientFactory seam
requires_bolts:
  - 008-telegram-bot-gateway
enables_bolts:
  - 010-conversational-booking-ops
requires_units: []
blocks: false
complexity:
  avg_complexity: 4
  avg_uncertainty: 3
  max_dependencies: 2
  testing_scope: 4
---

# Bolt: 009-user-access-and-keys

## Overview

Second bolt of intent 003. Turns the single-user daemon into a small self-hosted multi-user
service: schema v7 `users` table + user-scoped repositories, access modes (`owner`/`invite`),
hybrid LLM billing (owner key + per-user caps by default, optional encrypted personal key), and
owner admin commands.

**This bolt record covers the full unit's stories; only the US-029 slice (schema v7 multi-user
foundation) is implemented in this pass.** US-026 (access modes + router guard), US-027 (hybrid
billing + `/setkey`), and US-028 (owner admin commands) remain `status: ready` in their story
files and are picked up by a later pass of this same bolt — `current_stage: implement` reflects
that construction is ongoing, not that the bolt is complete.

## Objective

A multi-user-capable persistence foundation exists: every booking (and everything that inherits
scope through it — checks, savings, rebook sessions, traces) is tied to an owning user, migration
from the pre-v7 single-user schema is lossless and assigns existing data to the owner, and a
laptop (single-owner) deployment is provably unchanged in behavior. A per-user LLM client
resolution seam exists so the next slice (US-027) can swap in personal-key resolution without
touching check-path call sites.

## Stories Included (this bolt)

- **US-026**: Enforce access modes for a discoverable bot (Must) — not yet implemented
- **US-027**: Bring your own Anthropic key (Must) — not yet implemented
- **US-028**: Owner admin commands (Must) — not yet implemented
- **US-029**: User-scoped persistence, schema v7 (Must) — **implemented this pass**

## Bolt Type

**Type**: DDD Construction Bolt
**Definition**: `.specsmd/aidlc/templates/construction/bolt-types/ddd-construction-bolt.md`

## Stages

- ✅ **1. Domain Model**: Complete (full unit scope) → ddd-01-domain-model.md
- ✅ **2. Technical Design**: Complete (full unit scope) → ddd-02-technical-design.md
- 🔄 **3. Implement**: US-029 slice complete; US-026/027/028 pending a later pass
- ⏳ **4. Test**: US-029 slice tested (migration + isolation + factory); full-unit test report
  pending US-026/027/028

## Dependencies

### Requires
- Bolt 008 (telegram-bot-gateway) — router/dialog machine that US-026/027/028 hook into
  (not required for the US-029 persistence slice, which has no Telegram surface)
- intent-001 unit 001 (core-local-data) — SQLite migration framework (v6 → v7)
- intent-002 units — `LLMExtractor`/`AgentBrain` construction seam replaced by
  `LLMClientFactory`

### Enables
- Bolt 010 (conversational-booking-ops) — per-user registration/alert routing
- The rest of this bolt (US-026/027/028) — schema v7 is their foundation

## Success Criteria (US-029 slice)

- [x] Schema v7 adds `users` (exactly one `owner` row, enforced by a partial unique index) and
  `bookings.user_id` (NOT NULL FK, backfilled to the owner on migration)
- [x] A v6 database with existing bookings/checks/savings migrates so every booking belongs to
  the owner; a fresh init creates v7 directly with the owner already present
- [x] Laptop single-user mode (one user = the owner) behaves identically after migration
- [x] Repository APIs offer user-scoped listing methods (`list_active_for_user`,
  `list_all_for_user`, `SavingsRepository.list_all_for_user`); integration tests prove two users'
  bookings/savings never cross-leak
- [x] CLI commands (`register`, `bookings list`, `savings list`) resolve and operate as the owner
  user; behavior/output unchanged for a laptop deployment
- [x] `LLMClientFactory` seam introduced (`for_booking` / `agent_brain_for_booking`); check path
  goes through it; behavior unchanged (owner env-var key or DOM/scripted-only degradation)
- [ ] Access modes, invite codes, personal-key intake, admin commands — deferred to the next pass

## Notes

- Deliberately minimal: no key encryption, no invite codes, no access-mode enforcement in this
  pass — those are US-026/027/028, built by a later pass of this bolt (per the unit brief's
  recommended order, US-029 is step 1).
- `users.encrypted_key` (BLOB, nullable) exists in the schema now so the personal-key slice
  (US-027) needs no v8 migration; nothing reads/writes it yet.
- `BookingRepository.get_by_id` / `get_by_confirmation` / `set_occupancy` remain unscoped
  (looked up by an already-known, unguessable UUID/confirmation id from a trusted call site) —
  only the "list all" style reads that are actually exposed as owner-facing listings were scoped
  this pass. Documented as a known follow-up in ddd-02 if a stronger per-request scoping bound is
  needed once the bot gateway exposes untrusted routing.
