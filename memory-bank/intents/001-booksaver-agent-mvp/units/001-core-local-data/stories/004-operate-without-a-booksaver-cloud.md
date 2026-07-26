---
id: 004-operate-without-a-booksaver-cloud
status: complete
implemented: true
---

# US-013 Operate without a BookSaver cloud

**Intent:** `001-booksaver-agent-mvp`  
**Unit:** `001-core-local-data`  
**Status:** Ready  
**Tag:** MVP  
**Former grouping:** Operations and trust

## Story

**As a** user  
**I want** all booking and check data to stay on my machine  
**So that** I am not tied to a vendor account for a personal tool  

**Acceptance criteria**

- Given the daemon is running
- When checks and notifications occur
- Then booking details and history are read/written only to local persistence
- And there is no requirement to register with a centralized BookSaver service

---
