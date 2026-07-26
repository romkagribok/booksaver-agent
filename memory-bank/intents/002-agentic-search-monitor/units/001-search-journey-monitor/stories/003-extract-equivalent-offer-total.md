---
id: 003-extract-equivalent-offer-total
status: complete
implemented: true
---

# US-019 Extract equivalent offer total and feed savings pipeline

**Intent:** `002-agentic-search-monitor`
**Unit:** `001-search-journey-monitor`
**Status:** Ready
**Tag:** Phase 2

## Story

**As a** user
**I want** the check to find the cheapest still-refundable offer equivalent to my booking and compare it to what I paid
**So that** savings alerts reflect a real cancel-and-rebook opportunity

**Acceptance criteria**

- Given the verified property page's room/rate table
- When extraction runs
- Then candidate offers are parsed with room label, all-in bookable total (amount + ISO currency,
  including displayed taxes/charges), and raw cancellation-policy text
- And room-type equivalence to the registered `RoomType` is judged (DOM heuristics first, LLM judgment
  for naming drift) with a confidence score; candidates below threshold are excluded — never guessed
  into savings
- And non-refundable candidates and candidates for different dates/occupancy are excluded
- And the cheapest surviving candidate is emitted as a success `CheckResult` (live price, refund
  indicators, extraction method) consumed by the existing savings pipeline without interface changes
- And zero surviving candidates yields a coded failure (e.g. `NO_EQUIVALENT_OFFER`), which is not a
  savings signal
- And existing tests for savings detection, notifications, and guided rebook pass unchanged

---
