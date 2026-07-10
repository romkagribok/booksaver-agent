---
id: US-010
status: complete
implemented: true
---

# US-010 Start guided rebook only after explicit intent

**Intent:** `001-booksaver-agent-mvp`  
**Unit:** `004-guided-rebook`  
**Status:** Ready  
**Tag:** MVP  
**Former grouping:** Guided rebook (safety)

## Story

**As a** user  
**I want** to opt in before any rebook automation runs  
**So that** nothing is cancelled or purchased without my approval  

**Acceptance criteria**

- Given a savings alert
- When I have not started a rebook session
- Then the daemon performs no cancel or purchase actions
- When I explicitly start guided rebook for that booking id
- Then browser automation prepares the rebook path but waits at confirmation gates

---
