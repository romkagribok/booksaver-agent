---
id: US-005
status: complete
implemented: true
---

# US-005 Run scheduled browser check

**Intent:** `001-booksaver-agent-mvp`  
**Unit:** `002-booking-com-price-monitor`  
**Status:** Ready  
**Tag:** MVP  
**Former grouping:** Scheduled price check

## Story

**As a** user  
**I want** the daemon to periodically open my booking on Booking.com via browser automation  
**So that** I get an up-to-date live price without manual visits  

**Acceptance criteria**

- Given a registered booking and valid local session
- When the schedule triggers
- Then the daemon launches browser automation against Booking.com (not a travel API)
- And it navigates to the booking’s manage/view flow for that reservation
- And each run appends a check record (timestamp, outcome, raw price if parsed) to local storage
- And transient failures are logged and retried without deleting the booking

---
