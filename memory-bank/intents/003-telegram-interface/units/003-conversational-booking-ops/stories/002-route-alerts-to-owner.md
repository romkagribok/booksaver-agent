---
id: 002-route-alerts-to-owner
status: complete
implemented: true
---

# US-030 Route savings alerts to the booking owner

**Intent:** `003-telegram-interface`
**Unit:** `003-conversational-booking-ops`
**Status:** Complete
**Tag:** Phase 3

## Story

**As a** user
**I want** savings alerts for my bookings delivered to my own chat
**So that** I act on my opportunities and never see anyone else's

**Acceptance criteria**

- A detected savings opportunity notifies exactly the owning user's Telegram chat (replacing the single configured `telegram_chat_id` for bot-registered bookings)
- The alert includes property, dates, baseline vs found total, savings amount, refundability evidence summary, and how to start `/rebook`
- The owner's existing email channel keeps working for the owner's bookings if configured
- Notification failures are recorded per channel (existing behavior) and retried on the next detection, not spammed

---
