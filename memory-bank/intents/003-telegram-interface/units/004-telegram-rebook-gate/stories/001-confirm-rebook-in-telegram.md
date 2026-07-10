---
id: US-032
status: ready
implemented: false
---

# US-032 Confirm rebook steps in Telegram

**Intent:** `003-telegram-interface`
**Unit:** `004-telegram-rebook-gate`
**Status:** Ready
**Tag:** Phase 3

## Story

**As a** user acting on a savings alert
**I want** each mandatory rebook confirmation as an inline yes/no in my chat
**So that** the human gate works from my phone with a full audit trail

**Acceptance criteria**

- `/rebook <opportunity>` starts the existing rebook state machine (unchanged) with a Telegram `ConfirmationGate` adapter
- Every mandatory confirmation is one inline-keyboard prompt; only the owning user's tap counts
- The audit trail records channel=telegram, chat ID, message ID, and ISO-8601 timestamp per answer
- No answer within a configurable timeout aborts the session safely (state machine's abort path)
- Declining any step aborts; nothing is cancelled or purchased autonomously (existing guarantee preserved)

---
