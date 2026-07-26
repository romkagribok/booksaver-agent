---
id: 003-extract-booking-and-offer-data-with-llm
status: complete
implemented: true
---

# US-006 Extract booking and offer data with LLM

**Intent:** `001-booksaver-agent-mvp`  
**Unit:** `002-booking-com-price-monitor`  
**Status:** Ready  
**Tag:** MVP  
**Former grouping:** Scheduled price check

## Story

**As a** user  
**I want** the system to use an LLM to interpret complex booking pages  
**So that** price and policy details are extracted reliably when the DOM is messy  

**Acceptance criteria**

- Given a Booking.com page is loaded in the automated browser
- When structured selectors are insufficient or ambiguous
- Then the daemon invokes the configured LLM API with page context for extraction/reasoning
- And extracted fields include at minimum: current total price, currency, and cancellation/refund indicators
- And LLM API keys are read from local config only
- And extraction failures are logged and do not crash the daemon

---
