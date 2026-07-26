---
id: 001-run-booksaver-as-a-local-daemon
status: complete
implemented: true
---

# US-001 Run BookSaver as a local daemon

**Intent:** `001-booksaver-agent-mvp`  
**Unit:** `001-core-local-data`  
**Status:** Ready  
**Tag:** MVP  
**Former grouping:** Local daemon

## Story

**As a** user on my own computer  
**I want to** start and stop BookSaver as a background daemon  
**So that** price checks run on a schedule without me keeping a terminal open  

**Acceptance criteria**

- Given BookSaver is installed locally
- When I start the daemon with my local config
- Then it runs as a background process on my machine (not a remote service)
- And scheduled jobs run according to my configured interval
- And I can stop the daemon cleanly without corrupting local state

---
