---
id: US-025
status: complete
implemented: true
---

# US-025 Register a booking via chat dialog

**Intent:** `003-telegram-interface`
**Unit:** `003-conversational-booking-ops`
**Status:** Complete
**Tag:** Phase 3

## Story

**As a** user
**I want** to register my Booking.com reservation by answering the bot's questions
**So that** monitoring starts without any CLI access

**Acceptance criteria**

- `/register` starts a dialog collecting, one step at a time: property name (optionally property URL), check-in date, check-out date, room type, baseline all-in price + currency, refundability (must be refundable), occupancy (adults ≥ 1, children ≥ 0, rooms ≥ 1), confirmation ID
- Each answer is validated immediately with the same domain rules as CLI registration (hotels only, refundable only, future dates, valid occupancy); rejections re-prompt with the reason
- Before saving, the bot replays a full summary and requires an explicit yes; no is a safe abort
- A completed dialog calls the existing `register_booking` application service — one shared code path with the CLI — and the booking is owned by my user
- `/register` is available only to the owner and invited users (US-026); a per-user booking cap (default 3, config-overridable) is enforced with a polite message
- The booking appears in my `/bookings` and enters the check schedule

---
