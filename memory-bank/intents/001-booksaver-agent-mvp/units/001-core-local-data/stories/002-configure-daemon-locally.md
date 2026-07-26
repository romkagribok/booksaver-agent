---
id: 002-configure-daemon-locally
status: complete
implemented: true
---

# US-002 Configure daemon locally

**Intent:** `001-booksaver-agent-mvp`  
**Unit:** `001-core-local-data`  
**Status:** Ready  
**Tag:** MVP  
**Former grouping:** Local daemon

## Story

**As a** user  
**I want to** set schedule, paths, and notification settings in local config  
**So that** the tool behaves for my household without a cloud account  

**Acceptance criteria**

- Given a config file or local config directory on my machine
- When I set check interval, data directory, email, and Telegram settings
- Then the daemon loads them on startup
- And secrets are not committed to git or sent to a BookSaver-hosted backend
- And misconfiguration produces a clear local error message

---
