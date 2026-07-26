---
id: 003-per-user-limits
status: complete
implemented: true
---

# US-031 Per-user cost caps and abuse limits

**Intent:** `003-telegram-interface`
**Unit:** `003-conversational-booking-ops`
**Status:** Complete
**Tag:** Phase 3

## Story

**As the** bot owner
**I want** per-user ceilings on checks, LLM calls, and message rates
**So that** one user cannot hog the VPS or turn the bot into a spam target

**Acceptance criteria**

- Config defines per-user daily max checks and max LLM calls, and per-chat messages/minute; validated at load with safe defaults
- ADR-017 per-check caps remain unchanged underneath
- A breached ceiling produces one polite bot message and a recorded skipped/failed check — never silence, never a crash
- Scheduler iterates users fairly (round-robin across users, then their bookings); one user's slow checks do not starve others
- Rate-limited chats recover automatically in the next window

---
