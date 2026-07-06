# Story Index

Global index of BookSaver Agent stories after migration to the official specs.md AI-DLC memory bank.
Story file paths are relative to `memory-bank/intents/{intent}/units/`.

## 001-booksaver-agent-mvp

| Unit | Stories | Status |
|------|---------|--------|
| `001-core-local-data` | 4 stories | Complete |
| `002-booking-com-price-monitor` | 4 stories | Complete |
| `003-savings-detection-notifications` | 3 stories | Complete |
| `004-guided-rebook` | 3 stories | Complete |
| `005-extensibility-future` | 2 stories | Future |

### 001-core-local-data: Core & Local Data

| Story | Title | Tag | Status | File |
|-------|-------|-----|--------|------|
| `US-001` | Run BookSaver as a local daemon | MVP | Complete | `001-core-local-data/stories/001-run-booksaver-as-a-local-daemon.md` |
| `US-002` | Configure daemon locally | MVP | Complete | `001-core-local-data/stories/002-configure-daemon-locally.md` |
| `US-003` | Register a refundable Booking.com hotel | MVP | Complete | `001-core-local-data/stories/003-register-a-refundable-booking-com-hotel.md` |
| `US-013` | Operate without a BookSaver cloud | MVP | Complete | `001-core-local-data/stories/004-operate-without-a-booksaver-cloud.md` |

### 002-booking-com-price-monitor: Booking.com Price Monitor

| Story | Title | Tag | Status | File |
|-------|-------|-----|--------|------|
| `US-004` | Store Booking.com session locally | MVP | Complete | `002-booking-com-price-monitor/stories/001-store-booking-com-session-locally.md` |
| `US-005` | Run scheduled browser check | MVP | Complete | `002-booking-com-price-monitor/stories/002-run-scheduled-browser-check.md` |
| `US-006` | Extract booking and offer data with LLM | MVP | Complete | `002-booking-com-price-monitor/stories/003-extract-booking-and-offer-data-with-llm.md` |
| `US-014` | Handle check failures gracefully | MVP | Complete | `002-booking-com-price-monitor/stories/004-handle-check-failures-gracefully.md` |

### 003-savings-detection-notifications: Savings Detection & Notifications

| Story | Title | Tag | Status | File |
|-------|-------|-----|--------|------|
| `US-007` | Compare live price to baseline | MVP | Complete | `003-savings-detection-notifications/stories/001-compare-live-price-to-baseline.md` |
| `US-008` | Enforce pragmatic equivalence and refundability | MVP | Complete | `003-savings-detection-notifications/stories/002-enforce-pragmatic-equivalence-and-refundability.md` |
| `US-009` | Notify via email and Telegram | MVP | Complete | `003-savings-detection-notifications/stories/003-notify-via-email-and-telegram.md` |

### 004-guided-rebook: Guided Rebook

| Story | Title | Tag | Status | File |
|-------|-------|-----|--------|------|
| `US-010` | Start guided rebook only after explicit intent | MVP | Complete | `004-guided-rebook/stories/001-start-guided-rebook-only-after-explicit-intent.md` |
| `US-011` | Mandatory confirmation before cancel or purchase | MVP | Complete | `004-guided-rebook/stories/002-mandatory-confirmation-before-cancel-or-purchase.md` |
| `US-012` | Log rebook outcomes locally | MVP | Complete | `004-guided-rebook/stories/003-log-rebook-outcomes-locally.md` |

### 005-extensibility-future: Extensibility

| Story | Title | Tag | Status | File |
|-------|-------|-----|--------|------|
| `US-015` | Add a second booking platform | Future | Ready | `005-extensibility-future/stories/001-add-a-second-booking-platform.md` |
| `US-016` | Support non-hotel product types | Future | Ready | `005-extensibility-future/stories/002-support-non-hotel-product-types.md` |

## 002-agentic-search-monitor

| Unit | Stories | Status |
|------|---------|--------|
| `001-search-journey-monitor` | 3 stories | Complete (bolt 006) |
| `002-agentic-escalation` | 3 stories | Complete (bolt 007) |

### 001-search-journey-monitor: Search Journey Monitor

| Story | Title | Tag | Status | File |
|-------|-------|-----|--------|------|
| `US-017` | Capture occupancy at registration | Phase 2 | Complete | `001-search-journey-monitor/stories/001-capture-occupancy-at-registration.md` |
| `US-018` | Run scripted search journey to verified property page | Phase 2 | Complete | `001-search-journey-monitor/stories/002-run-scripted-search-journey.md` |
| `US-019` | Extract equivalent offer total and feed savings pipeline | Phase 2 | Complete | `001-search-journey-monitor/stories/003-extract-equivalent-offer-total.md` |

### 002-agentic-escalation: Agentic Escalation

| Story | Title | Tag | Status | File |
|-------|-------|-----|--------|------|
| `US-020` | LLM browser agent takes over failed journey steps | Phase 2 | Complete | `002-agentic-escalation/stories/001-llm-agent-step-takeover.md` |
| `US-021` | Enforce action guard and hard cost caps | Phase 2 | Complete | `002-agentic-escalation/stories/002-action-guard-and-hard-caps.md` |
| `US-022` | Trace and inspect agent runs locally | Phase 2 | Complete | `002-agentic-escalation/stories/003-trace-and-inspect-agent-runs.md` |

## Summary

| Intent | Units | Stories | Status |
|--------|-------|---------|--------|
| `001-booksaver-agent-mvp` | 5 | 16 | MVP complete (14/14 MVP stories); Unit 5 (extensibility) is post-MVP |
| `002-agentic-search-monitor` | 2 | 6 | Complete (bolts 006–007; 345 tests) |

All 22 stories (16 original + 6 Phase 2) are assigned exactly once.
