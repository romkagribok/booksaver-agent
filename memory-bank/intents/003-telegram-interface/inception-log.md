---
intent: 003-telegram-interface
created: 2026-07-10T02:15:00Z
status: pending-validation
---

# Inception Log: telegram-interface

## Overview

**Intent**: Make a Telegram bot the primary user interface — daemon on an owner-operated VPS; users
register bookings, manage their own Anthropic API key, receive alerts, and confirm rebooks entirely
in chat. Discoverable-bot safety via access modes + bring-your-own-key.
**Type**: brown-field (enhancement + deliberate scope amendment of the local-only constraint)
**Created**: 2026-07-10T02:15:00Z

## Artifacts Created

| Artifact | Status | File |
|----------|--------|------|
| Requirements | ✅ draft | requirements.md |
| System Context | ✅ draft | system-context.md |
| Units | ✅ draft | units.md + units/*/unit-brief.md |
| Stories | ✅ draft | units/*/stories/*.md (US-023 – US-036) |
| Bolt Plan | Planned (not yet created) | bolts 008–012, one per unit, created at construction start |

## Summary

| Metric | Count |
|--------|-------|
| Functional Requirements | 8 |
| Non-Functional Requirements | 3 groups |
| Units | 5 |
| Stories | 14 |
| Bolts Planned | 5 (008–012) |

## Units Breakdown

| Unit | Stories | Bolt | Priority |
|------|---------|------|----------|
| 001-telegram-bot-gateway | US-023, US-024, US-036 | 008 | Must |
| 002-user-access-and-keys | US-026, US-027, US-028, US-029 | 009 | Must |
| 003-conversational-booking-ops | US-025, US-030, US-031 | 010 | Must |
| 004-telegram-rebook-gate | US-032, US-033 | 011 | Must |
| 005-vps-deployment | US-034, US-035 | 012 | Must (cookie import Should) |

## Decision Log (pending user validation — Checkpoint 1)

| Date | Decision | Rationale | Approved |
|------|----------|-----------|----------|
| 2026-07-10T02:15:00Z | Amend "local-only" to "self-hosted, owner-operated VPS; no BookSaver cloud" (proposed ADR-018); laptop mode remains supported | User direction: daemon on a VPS, bot as main interface | Pending |
| 2026-07-10T02:15:00Z | Access model: modes owner/invite/open; in open mode, LLM features locked behind bring-your-own Anthropic key | User direction: discoverable bot must not spend owner's budget | Pending |
| 2026-07-10T02:15:00Z | Telegram transport: stdlib long polling (extends ADR-011); no bot framework, no async | Consistent with stdlib-first (ADR-003) and sync design (ADR-008) | Pending |
| 2026-07-10T02:15:00Z | User keys encrypted at rest (proposed: Fernet via `cryptography` dep + `BOOKSAVER_SECRET_KEY` env var) | Plaintext keys of *other people* on the owner's VPS is unacceptable; stdlib has no real symmetric crypto | Pending — dep addition needs approval |
| 2026-07-10T02:15:00Z | VPS session strategy: logged-out public prices by default; optional cookie import for member rates | Headed `booksaver auth` impossible on display-less VPS | Pending |
| 2026-07-10T02:15:00Z | Rebook final click via device-handoff deep link to the user's own device | Preserves no-autonomous-purchase; VPS browser never books/cancels | Pending |
| 2026-07-10T02:15:00Z | Schema v7: users table + user_id scoping; migration assigns existing rows to owner | Multi-user isolation by construction; laptop mode is the one-user degenerate case | Pending |

## Ready for Construction

**Checklist**:
- [x] All requirements documented (draft)
- [x] System context defined (draft)
- [x] Units decomposed (draft)
- [x] Stories created for all units (draft)
- [ ] Bolts created (at construction start, after validation)
- [ ] Human review complete — **awaiting Checkpoint 1 discussion** (open questions in requirements.md)

## Dependencies

Bolt 008 → 009 → 010 → 011; 012 depends on 010 (fully usable) but is deployable owner-only after 008.
All depend on intents 001–002 code (bolts 001–007); savings/rebook state machines are frozen
regression surfaces — only new adapters plug into their existing ports.
