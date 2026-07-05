---
id: US-008
status: Ready
implemented: false
---

# US-008 Enforce pragmatic equivalence and refundability

**Intent:** `001-booksaver-agent-mvp`  
**Unit:** `003-savings-detection-notifications`  
**Status:** Ready  
**Tag:** MVP  
**Former grouping:** Compare and detect savings

## Story

**As a** user  
**I want** “cheaper” to mean same stay and room, still refundable  
**So that** I am not pushed toward worse or non-refundable deals  

**Acceptance criteria**

- Given a candidate live offer
- When dates differ from my registered check-in/out
- Then it is rejected as not equivalent
- When property or room type differs
- Then it is rejected as not equivalent
- When cancellation terms are not refundable (free cancellation / refundable policy absent per extraction)
- Then it is rejected even if price is lower
- When dates, property, and room match and offer is refundable
- Then it may proceed to notification (policy tier may differ from original if still refundable)

---
