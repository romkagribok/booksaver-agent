---
id: 003-register-a-refundable-booking-com-hotel
status: complete
implemented: true
---

# US-003 Register a refundable Booking.com hotel

**Intent:** `001-booksaver-agent-mvp`  
**Unit:** `001-core-local-data`  
**Status:** Ready  
**Tag:** MVP  
**Former grouping:** Register booking

## Story

**As a** user  
**I want to** register an existing Booking.com hotel booking for monitoring  
**So that** the daemon knows what to watch and my original price baseline  

**Acceptance criteria**

- Given I have a refundable hotel reservation on Booking.com
- When I register the booking (confirmation id, dates, property, room type, amount paid, refundability note)
- Then the booking is stored in local persistence
- And the original total price and currency are recorded as the baseline
- And only Booking.com hotel bookings are accepted in MVP (other types rejected with clear message)

---
