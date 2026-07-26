---
id: 004-handle-check-failures-gracefully
status: complete
implemented: true
---

# US-014 Handle check failures gracefully

**Intent:** `001-booksaver-agent-mvp`  
**Unit:** `002-booking-com-price-monitor`  
**Status:** Ready  
**Tag:** MVP  
**Former grouping:** Operations and trust

## Story

**As a** user  
**I want** failed checks to be visible but non-fatal  
**So that** one broken session does not delete my monitoring setup  

**Acceptance criteria**

- Given a check fails (network, captcha, layout change, LLM error)
- When the run ends
- Then failure reason is logged locally
- And the booking remains registered for the next scheduled run
- And repeated failures can trigger a local warning (configurable threshold) — MVP: log + optional single alert

---
