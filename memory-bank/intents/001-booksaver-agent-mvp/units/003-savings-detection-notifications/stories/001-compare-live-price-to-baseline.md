---
id: US-007
status: complete
implemented: true
---

# US-007 Compare live price to baseline

**Intent:** `001-booksaver-agent-mvp`  
**Unit:** `003-savings-detection-notifications`  
**Status:** Ready  
**Tag:** MVP  
**Former grouping:** Compare and detect savings

## Story

**As a** user  
**I want** the daemon to compare the live equivalent offer to what I paid  
**So that** I only hear about real savings opportunities  

**Acceptance criteria**

- Given a successful check with parsed live price
- When live total is strictly less than my stored baseline (same currency)
- Then the booking is flagged as a potential savings opportunity
- When live total is greater or equal
- Then no savings alert is raised for that run

---
