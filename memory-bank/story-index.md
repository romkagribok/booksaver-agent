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

## 003-telegram-interface

| Unit | Stories | Status |
|------|---------|--------|
| `001-telegram-bot-gateway` | 3 stories | Complete (bolt 008) |
| `002-user-access-and-keys` | 4 stories | Complete (bolt 009) |
| `003-conversational-booking-ops` | 3 stories | Complete (bolt 010) |
| `004-telegram-rebook-gate` | 2 stories | Complete (bolt 011) |
| `005-vps-deployment` | 2 stories | Complete (bolt 012) |

### 001-telegram-bot-gateway: Telegram Bot Gateway

| Story | Title | Tag | Status | File |
|-------|-------|-----|--------|------|
| `US-023` | Run Telegram update loop inside the daemon | Phase 3 | Complete | `001-telegram-bot-gateway/stories/001-run-telegram-update-loop.md` |
| `US-024` | Route commands and multi-step dialogs | Phase 3 | Complete | `001-telegram-bot-gateway/stories/002-route-commands-and-dialogs.md` |
| `US-036` | Inspect daemon health and history from chat | Phase 3 | Complete | `001-telegram-bot-gateway/stories/003-inspect-daemon-from-chat.md` |

### 002-user-access-and-keys: User Access & Keys

| Story | Title | Tag | Status | File |
|-------|-------|-----|--------|------|
| `US-026` | Enforce access modes for a discoverable bot | Phase 3 | Complete | `002-user-access-and-keys/stories/001-enforce-access-modes.md` |
| `US-027` | Optional personal Anthropic API key (hybrid billing) | Phase 3 | Complete | `002-user-access-and-keys/stories/002-bring-your-own-anthropic-key.md` |
| `US-028` | Owner admin commands | Phase 3 | Complete | `002-user-access-and-keys/stories/003-owner-admin-commands.md` |
| `US-029` | User-scoped persistence (schema v7) | Phase 3 | Complete | `002-user-access-and-keys/stories/004-user-scoped-persistence.md` |

### 003-conversational-booking-ops: Conversational Booking Ops

| Story | Title | Tag | Status | File |
|-------|-------|-----|--------|------|
| `US-025` | Register a booking via chat dialog | Phase 3 | Complete | `003-conversational-booking-ops/stories/001-register-booking-via-chat.md` |
| `US-030` | Route savings alerts to the booking owner | Phase 3 | Complete | `003-conversational-booking-ops/stories/002-route-alerts-to-owner.md` |
| `US-031` | Per-user cost caps and abuse limits | Phase 3 | Complete | `003-conversational-booking-ops/stories/003-per-user-limits.md` |

### 004-telegram-rebook-gate: Telegram Rebook Gate

| Story | Title | Tag | Status | File |
|-------|-------|-----|--------|------|
| `US-032` | Confirm rebook steps in Telegram | Phase 3 | Complete | `004-telegram-rebook-gate/stories/001-confirm-rebook-in-telegram.md` |
| `US-033` | Device handoff for the final booking click | Phase 3 | Complete | `004-telegram-rebook-gate/stories/002-device-handoff-final-click.md` |

### 005-vps-deployment: VPS Deployment

| Story | Title | Tag | Status | File |
|-------|-------|-----|--------|------|
| `US-034` | Deploy daemon and bot on a VPS | Phase 3 | Complete | `005-vps-deployment/stories/001-deploy-on-vps.md` |
| `US-035` | Logged-out checks with optional cookie import | Phase 3 | Complete | `005-vps-deployment/stories/002-logged-out-checks-and-cookie-import.md` |

## 004-production-hardening

| Unit | Stories | Status |
|------|---------|--------|
| `001-production-reliability` | 5 stories | Complete (bolts 013–014) |

### 001-production-reliability: Production Reliability

| Story | Title | Tag | Status | File |
|-------|-------|-----|--------|------|
| `US-037` | Adapt after repeated browser actions | Production Hardening | Complete | `001-production-reliability/stories/001-adapt-after-repeated-browser-actions.md` |
| `US-038` | Continue `fill_search` from trusted booking data | Production Hardening | Complete | `001-production-reliability/stories/002-continue-fill-search-from-trusted-data.md` |
| `US-039` | Package the persistence schema | Production Hardening | Complete | `001-production-reliability/stories/003-package-persistence-schema.md` |
| `US-040` | Discover commands and use displayed booking identifiers | Production Hardening | Complete | `001-production-reliability/stories/004-discover-commands-and-use-booking-prefixes.md` |
| `US-041` | Enter search from trusted query | Production Hardening | Complete | `001-production-reliability/stories/005-enter-search-from-trusted-query.md` |

## Summary

| Intent | Units | Stories | Status |
|--------|-------|---------|--------|
| `001-booksaver-agent-mvp` | 5 | 16 | MVP complete (14/14 MVP stories); Unit 5 (extensibility) is post-MVP |
| `002-agentic-search-monitor` | 2 | 6 | Complete (bolts 006–007; 345 tests) |
| `003-telegram-interface` | 5 | 14 | Complete (bolts 008–012; all 14 stories US-023–036) |
| `004-production-hardening` | 1 | 5 | Complete (bolts 013–014; 633 tests after query-entry correction) |

All 41 stories (16 original + 6 Phase 2 + 14 Phase 3 + 5 production-hardening) are assigned exactly once.
