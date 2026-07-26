---
id: 002-device-handoff-final-click
status: complete
implemented: true
---

# US-033 Device handoff for the final booking click

**Intent:** `003-telegram-interface`
**Unit:** `004-telegram-rebook-gate`
**Status:** Complete (bolt 011)
**Tag:** Phase 3

## Story

**As a** user completing a rebook
**I want** the bot to hand me a link that opens the exact new offer on my own device
**So that** I make the final booking myself — the VPS never books or cancels anything

**Acceptance criteria**

- After the confirmation steps, the bot sends a deep link to the property page carrying the opportunity's check-in/check-out dates and occupancy
- The link is verified to reproduce the property (same property ID/slug as the verified journey page)
- The bot then asks whether I completed the booking (and separately, the old booking's cancellation); my answers are logged to the existing rebook log with timestamps
- Guidance reminds me to confirm the new rate is refundable at checkout before paying
- The VPS browser performs no cancel/checkout navigation at any point (ActionGuard untouched)

---
