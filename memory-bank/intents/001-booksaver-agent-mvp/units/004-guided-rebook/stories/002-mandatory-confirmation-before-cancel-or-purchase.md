---
id: 002-mandatory-confirmation-before-cancel-or-purchase
status: complete
implemented: true
---

# US-011 Mandatory confirmation before cancel or purchase

**Intent:** `001-booksaver-agent-mvp`  
**Unit:** `004-guided-rebook`  
**Status:** Ready  
**Tag:** MVP  
**Former grouping:** Guided rebook (safety)

## Story

**As a** user  
**I want** a clear confirmation step before cancel or new booking  
**So that** I remain in control of money and itinerary changes  

**Acceptance criteria**

- Given an active guided rebook session
- When the flow reaches a cancel-existing or confirm-new-booking action
- Then the daemon stops and presents what will happen (old vs new price, refundability summary)
- And it requires explicit yes/no confirmation from me in the local interface
- When I decline
- Then no cancel or charge occurs and the session ends safely
- When I confirm
- Then automation may proceed only for that single approved action
- And each subsequent destructive step requires a new confirmation

---
