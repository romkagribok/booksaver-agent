---
id: US-009
status: complete
implemented: true
---

# US-009 Notify via email and Telegram

**Intent:** `001-booksaver-agent-mvp`  
**Unit:** `003-savings-detection-notifications`  
**Status:** Ready  
**Tag:** MVP  
**Former grouping:** Notify user

## Story

**As a** user  
**I want** email and Telegram alerts when savings are found  
**So that** I can act before the rate changes again  

**Acceptance criteria**

- Given a validated savings opportunity
- When notification runs
- Then I receive an email with booking id, baseline vs live price, and percent/amount saved
- And I receive a Telegram message with the same core facts
- And messages include a pointer to start the guided rebook flow (local CLI or documented command)
- And notification failures for one channel do not block the other (both attempted; failures logged)

---
