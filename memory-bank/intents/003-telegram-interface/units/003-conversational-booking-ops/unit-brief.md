# Unit Brief: Conversational Booking Ops

**Unit ID:** `003-conversational-booking-ops`
**Intent:** `003-telegram-interface`
**Status:** Complete (bolt 010)
**Build order:** 3

## Purpose

Make Telegram the full write-path for monitoring: a `/register` guided dialog that collects property,
dates, room type, baseline price, refundability, occupancy, and confirmation ID — validated by the
same domain rules as the CLI and ending in the same `Booking` aggregate; savings alerts routed to the
booking owner's chat; per-user daily caps, per-chat rate limits, and fair scheduling so one user
cannot starve others.

## Dependencies on other units

| Unit | What this unit needs |
|------|----------------------|
| `002-user-access-and-keys` | User identity + access enforcement (only owner/invited users may register); per-user LLM client factory |
| intent-001 `001-core-local-data` | `register_booking` application service (shared CLI/bot path), occupancy validation |
| intent-001 `003-savings-detection-notifications` | Notifier wiring — replace single-chat alert with per-user routing |
| intent-002 | Scheduler iteration + ADR-017 caps to extend with per-user ceilings |

## Loose coupling / interfaces (design-level)

| Consumes | From |
|----------|------|
| Dialog machine, user identity | units 001–002 |
| `register_booking(...)`, savings/check repositories | existing application layer |

| Emits | To |
|-------|-----|
| User-owned `Booking` rows | persistence |
| `AlertRoute(user_id -> chat_id)` | notification dispatch |
| Per-user limit breaches (polite bot message + skipped check record) | scheduler, check history |

## Recommended implementation order (within unit)

1. US-025 — `/register` dialog (validation per step, summary + final confirm, `/cancelflow`)
2. US-030 — per-user alert routing (owner keeps email too if configured)
3. US-031 — per-user daily caps, per-chat rate limits, fair scheduling

## Completion criteria (unit-level)

- A brand-new invited user goes `/start` → invite code → `/register` → first scheduled check
  entirely in chat (owner-billed; `/setkey` optional at any point).
- Refundable-only / hotels-only rejections mid-dialog use the same messages as the CLI.
- A savings alert reaches only the owning user's chat.
- Limit breaches are polite and visible; other users' schedules unaffected.

---

## Story Files

- `US-025`
- `US-030`
- `US-031`
