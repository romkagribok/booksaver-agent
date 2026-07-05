---
id: US-012
status: complete
implemented: true
---

# US-012 Log rebook outcomes locally

**Intent:** `001-booksaver-agent-mvp`  
**Unit:** `004-guided-rebook`  
**Status:** Ready  
**Tag:** MVP  
**Former grouping:** Guided rebook (safety)

## Story

**As a** user  
**I want** a local audit trail of rebook attempts  
**So that** I can troubleshoot what the agent did on my behalf  

**Acceptance criteria**

- Given any guided rebook session
- When steps complete or fail
- Then events (started, confirmation requested, confirmed, cancelled by user, completed, error) are appended to local logs/storage
- And logs stay on my machine

---
