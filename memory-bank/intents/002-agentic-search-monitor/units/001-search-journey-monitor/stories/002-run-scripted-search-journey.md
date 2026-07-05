---
id: US-018
status: Ready
implemented: false
---

# US-018 Run scripted search journey to verified property page

**Intent:** `002-agentic-search-monitor`
**Unit:** `001-search-journey-monitor`
**Status:** Ready
**Tag:** Phase 2

## Story

**As a** user
**I want** the daemon to re-search my property and dates on Booking.com the way I would
**So that** checks see real, bookable prices for a new reservation instead of my old reservation figure

**Acceptance criteria**

- Given an active booking with occupancy and a valid saved session
- When the schedule triggers a check
- Then the daemon restores session cookies and performs the full journey: open booking.com, dismiss
  known interstitials (cookie/consent banners), enter the property-name query, set exact
  check-in/check-out dates and the booking's occupancy, submit the search
- And it locates the registered property in the results and verifies identity (name/ref match) before
  opening the property page — a look-alike or missing property yields a coded failure, never a price
- And on the property page it verifies the displayed dates and occupancy match the booking before any
  extraction
- And the journey is decomposed into named steps, each reporting success/failure with a reason
  (the Unit 2 escalation points)
- And no deep-link shortcut is used; the manage page is not visited for prices
- And refreshed cookies are persisted after the run; auth loss yields `AUTH_REQUIRED` as in MVP, and a
  bot-detection/captcha wall yields its own distinct failure code

---
