---
id: 001-preserve-opportunity-across-technical-failures
unit: 001-conclusive-opportunity-lifecycle
intent: 018-conclusive-rebook-opportunity-lifecycle
status: complete
priority: must
created: 2026-07-27T02:32:08.000Z
assigned_bolt: 033-conclusive-opportunity-lifecycle
implemented: true
---

# Story: Preserve Opportunity Across Technical Failures

**Global story ID**: US-109

## User Story

**As a** user whose latest price check failed technically
**I want** the last successfully verified saving to remain available
**So that** transient automation trouble does not erase useful market evidence.

## Acceptance Criteria

- [x] One or more non-conclusive failures after a positive check preserve that opportunity.
- [x] Authentication, timeout, extraction, currency, bot-wall, agent, and unknown failures are
      non-conclusive.
- [x] The opportunity retains its original validation time and check ID.
- [x] Telegram shows the original successful verification time and explains that technical failures
      do not update it.
- [x] No historical row is changed or deleted.

## Dependencies

Intent 017 current-opportunity selection and existing check history.
