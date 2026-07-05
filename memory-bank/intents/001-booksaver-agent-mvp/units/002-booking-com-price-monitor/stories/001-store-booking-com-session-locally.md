---
id: US-004
status: Ready
implemented: false
---

# US-004 Store Booking.com session locally

**Intent:** `001-booksaver-agent-mvp`  
**Unit:** `002-booking-com-price-monitor`  
**Status:** Ready  
**Tag:** MVP  
**Former grouping:** Register booking

## Story

**As a** user  
**I want to** authenticate to Booking.com in a browser context the daemon controls  
**So that** automated checks can reach my manage-booking pages  

**Acceptance criteria**

- Given browser automation is configured
- When I complete login (or refresh session) through the supported local flow
- Then session cookies or credentials are stored only on my machine
- And the daemon can reuse the session for scheduled checks until expiry
- And session expiry surfaces a local alert telling me to re-authenticate

---
