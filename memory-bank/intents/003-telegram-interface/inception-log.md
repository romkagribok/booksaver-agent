---
intent: 003-telegram-interface
created: 2026-07-10T02:15:00Z
status: validated
updated: 2026-07-11T17:39:20Z
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

## Decision Log — Checkpoint 1 validated with user 2026-07-11T17:39:20Z

| Date | Decision | Rationale | Approved |
|------|----------|-----------|----------|
| 2026-07-10T02:15:00Z | Amend "local-only" to "self-hosted, owner-operated (laptop or VPS); no BookSaver cloud" (ADR-018, written in bolt 008); laptop mode remains supported | User direction: daemon on a VPS, bot as main interface | ✅ 2026-07-11 |
| 2026-07-11T17:39:20Z | Access model: modes `owner`/`invite` only — the drafted `open` mode is **cut from scope**; repo stays open-source with a personal-use disclaimer | Operating a publicly available bot = operating a scraping service for third parties (ToS exposure) and concentrates all traffic on one IP; strangers self-host instead | ✅ 2026-07-11 |
| 2026-07-11T17:39:20Z | LLM billing: **hybrid** — invited users owner-billed by default under per-user daily caps; optional personal key via `/setkey` | Removes onboarding friction for trusted users while keeping the encrypted key store and cost fairness option | ✅ 2026-07-11 |
| 2026-07-10T02:15:00Z | Telegram transport: stdlib long polling (extends ADR-011); no bot framework, no async | Consistent with stdlib-first (ADR-003) and sync design (ADR-008) | ✅ 2026-07-11 |
| 2026-07-10T02:15:00Z | User keys encrypted at rest: Fernet via `cryptography` dep + `BOOKSAVER_SECRET_KEY` env var | Plaintext keys of *other people* on the owner's VPS is unacceptable; stdlib has no real symmetric crypto | ✅ 2026-07-11 — dep addition approved |
| 2026-07-10T02:15:00Z | VPS session strategy: logged-out public prices by default; optional cookie import for member rates. Logged-out mode lands in Wave 1 so the VPS-IP smoke test can run early | Headed `booksaver auth` impossible on display-less VPS | ✅ 2026-07-11 |
| 2026-07-11T17:39:20Z | Deployment: **VPS-first, validate the IP early** — smoke-test the Booking.com journey from the actual VPS IP immediately after bolt-008/012 scaffolding lands; runbook documents fallbacks (home server, lower frequency, residential proxy) | Datacenter IPs are prone to Booking.com bot-walls; find out before building bolts 010–011 on top | ✅ 2026-07-11 |
| 2026-07-10T02:15:00Z | Rebook final click via device-handoff deep link to the user's own device | Preserves no-autonomous-purchase; VPS browser never books/cancels | ✅ 2026-07-11 |
| 2026-07-10T02:15:00Z | Schema v7: users table + user_id scoping; migration assigns existing rows to owner | Multi-user isolation by construction; laptop mode is the one-user degenerate case | ✅ 2026-07-11 |
| 2026-07-11T17:39:20Z | Per-user booking cap, default 3 (config-overridable) | Bounds VPS browser compute per user | ✅ 2026-07-11 |

## Ready for Construction

**Checklist**:
- [x] All requirements documented (draft)
- [x] System context defined (draft)
- [x] Units decomposed (draft)
- [x] Stories created for all units (draft)
- [ ] Bolts created (at construction start)
- [x] Human review complete — Checkpoint 1 validated 2026-07-11T17:39:20Z (all open questions in requirements.md resolved; `open` access mode cut; hybrid billing; VPS-first with early IP validation)

## Dependencies

Bolt 008 → 009 → 010 → 011; 012 depends on 010 (fully usable) but is deployable owner-only after 008.
All depend on intents 001–002 code (bolts 001–007); savings/rebook state machines are frozen
regression surfaces — only new adapters plug into their existing ports.
