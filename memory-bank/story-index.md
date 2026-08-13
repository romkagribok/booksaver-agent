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
| `001-production-reliability` | 6 stories | Complete (bolts 013–015) |

### 001-production-reliability: Production Reliability

| Story | Title | Tag | Status | File |
|-------|-------|-----|--------|------|
| `US-037` | Adapt after repeated browser actions | Production Hardening | Complete | `001-production-reliability/stories/001-adapt-after-repeated-browser-actions.md` |
| `US-038` | Continue `fill_search` from trusted booking data | Production Hardening | Complete | `001-production-reliability/stories/002-continue-fill-search-from-trusted-data.md` |
| `US-039` | Package the persistence schema | Production Hardening | Complete | `001-production-reliability/stories/003-package-persistence-schema.md` |
| `US-040` | Discover commands and use displayed booking identifiers | Production Hardening | Complete | `001-production-reliability/stories/004-discover-commands-and-use-booking-prefixes.md` |
| `US-041` | Enter search from trusted query | Production Hardening | Complete | `001-production-reliability/stories/005-enter-search-from-trusted-query.md` |
| `US-042` | Handle property availability page | Production Hardening | Complete | `001-production-reliability/stories/006-handle-property-availability-page.md` |

## 005-telegram-command-navigation

| Unit | Stories | Status |
|------|---------|--------|
| `001-interactive-command-navigation` | 5 stories | Complete (bolts 016 and 018) |

### 001-interactive-command-navigation: Interactive Command Navigation

| Story | Title | Tag | Status | File |
|-------|-------|-----|--------|------|
| `US-043` | Discover applicable commands natively | Command Navigation | Complete | `001-interactive-command-navigation/stories/001-discover-applicable-commands-natively.md` |
| `US-044` | Route and authorize interactive callbacks | Command Navigation | Complete | `001-interactive-command-navigation/stories/002-route-and-authorize-interactive-callbacks.md` |
| `US-045` | Select bookings and savings opportunities | Command Navigation | Complete | `001-interactive-command-navigation/stories/003-select-bookings-and-savings-opportunities.md` |
| `US-046` | Navigate owner administration safely | Command Navigation | Complete | `001-interactive-command-navigation/stories/004-navigate-owner-administration-safely.md` |
| `US-047` | Handle Boolean Telegram action results | Command Navigation | Complete | `001-interactive-command-navigation/stories/005-handle-boolean-telegram-action-results.md` |

## 006-telegram-booking-management

| Unit | Stories | Status |
|------|---------|--------|
| `001-conversational-booking-management` | 4 stories | Complete (bolt 017) |

### 001-conversational-booking-management: Conversational Booking Management

| Story | Title | Tag | Status | File |
|-------|-------|-----|--------|------|
| `US-048` | Discover booking management commands | Booking Management | Complete | `001-conversational-booking-management/stories/001-discover-booking-management-commands.md` |
| `US-049` | Edit an owned booking selectively | Booking Management | Complete | `001-conversational-booking-management/stories/002-edit-owned-booking-selectively.md` |
| `US-050` | Delete an owned booking after confirmation | Booking Management | Complete | `001-conversational-booking-management/stories/003-delete-owned-booking-after-confirmation.md` |
| `US-051` | Preserve booking mutation integrity | Booking Management | Complete | `001-conversational-booking-management/stories/004-preserve-booking-mutation-integrity.md` |

## 007-telegram-on-demand-checks

| Unit | Stories | Status |
|------|---------|--------|
| `001-on-demand-check-orchestration` | 5 stories | Complete (bolt 019) |

### 001-on-demand-check-orchestration: On-Demand Check Orchestration

| Story | Title | Tag | Status | File |
|-------|-------|-----|--------|------|
| `US-052` | Discover and select an immediate check | On-Demand Check | Complete | `001-on-demand-check-orchestration/stories/001-discover-and-select-immediate-check.md` |
| `US-053` | Run a responsive background check | On-Demand Check | Complete | `001-on-demand-check-orchestration/stories/002-run-responsive-background-check.md` |
| `US-054` | Serialize all check work | On-Demand Check | Complete | `001-on-demand-check-orchestration/stories/003-serialize-all-check-work.md` |
| `US-055` | Share daily check and LLM budgets | On-Demand Check | Complete | `001-on-demand-check-orchestration/stories/004-share-daily-check-and-llm-budgets.md` |
| `US-056` | Reuse the normal monitoring pipeline | On-Demand Check | Complete | `001-on-demand-check-orchestration/stories/005-reuse-normal-monitoring-pipeline.md` |

## 008-currency-aligned-price-checks

| Unit | Stories | Status |
|------|---------|--------|
| `001-currency-alignment-recovery` | 5 stories | Complete (bolt 020) |

### 001-currency-alignment-recovery: Currency Alignment Recovery

| Story | Title | Tag | Status | File |
|-------|-------|-----|--------|------|
| `US-057` | Propagate baseline currency through trusted navigation | Currency Alignment | Complete | `001-currency-alignment-recovery/stories/001-propagate-baseline-currency.md` |
| `US-058` | Verify rendered candidate currencies | Currency Alignment | Complete | `001-currency-alignment-recovery/stories/002-verify-rendered-currency.md` |
| `US-059` | Recover an otherwise-valid currency mismatch once | Currency Alignment | Complete | `001-currency-alignment-recovery/stories/003-recover-currency-once.md` |
| `US-060` | Report unresolved currency alignment safely | Currency Alignment | Complete | `001-currency-alignment-recovery/stories/004-report-unresolved-currency.md` |
| `US-061` | Preserve the shared check pipeline and safety gates | Currency Alignment | Complete | `001-currency-alignment-recovery/stories/005-preserve-shared-check-pipeline.md` |

## 009-invite-first-sharing

| Unit | Stories | Status |
|------|---------|--------|
| `001-invite-first-access` | 5 stories | Complete (bolt 021; 763 tests at final verification) |

### 001-invite-first-access: Invite-First Access

| Story | Title | Tag | Status | File |
|-------|-------|-----|--------|------|
| `US-062` | Deliver a copyable invite command | Invite-First Sharing | Complete | `001-invite-first-access/stories/001-deliver-copyable-invite-command.md` |
| `US-063` | Maintain recognizable Telegram usernames | Invite-First Sharing | Complete | `001-invite-first-access/stories/002-maintain-recognizable-usernames.md` |
| `US-064` | Enforce invite-only non-owner admission | Invite-First Sharing | Complete | `001-invite-first-access/stories/003-enforce-invite-only-admission.md` |
| `US-065` | Explain revoked access | Invite-First Sharing | Complete | `001-invite-first-access/stories/004-explain-revoked-access.md` |
| `US-066` | Preserve sharing safety | Invite-First Sharing | Complete | `001-invite-first-access/stories/005-preserve-sharing-safety.md` |

## 010-telegram-privacy-boundaries

| Unit | Stories | Status |
|------|---------|--------|
| `001-telegram-privacy-boundaries` | 5 stories | Complete (bolt 022; 763 tests at final verification) |

### 001-telegram-privacy-boundaries: Telegram Privacy Boundaries

| Story | Title | Tag | Status | File |
|-------|-------|-----|--------|------|
| `US-067` | Restrict interaction to private chats | Telegram Privacy | Complete | `001-telegram-privacy-boundaries/stories/001-restrict-interaction-to-private-chats.md` |
| `US-068` | Scope status and selectors | Telegram Privacy | Complete | `001-telegram-privacy-boundaries/stories/002-scope-status-and-selectors.md` |
| `US-069` | Show aggregate admin usage | Telegram Privacy | Complete | `001-telegram-privacy-boundaries/stories/003-show-aggregate-admin-usage.md` |
| `US-070` | Stop work after revocation | Telegram Privacy | Complete | `001-telegram-privacy-boundaries/stories/004-stop-work-after-revocation.md` |
| `US-071` | Prove cross-user isolation | Telegram Privacy | Complete | `001-telegram-privacy-boundaries/stories/005-prove-cross-user-isolation.md` |

## 011-post-rebook-monitoring

| Unit | Stories | Status |
|------|---------|--------|
| `001-post-rebook-monitoring` | 5 stories | Complete (bolt 023; 788 tests) |

### 001-post-rebook-monitoring: Post-Rebook Monitoring

| Story | Title | Tag | Status | File |
|-------|-------|-----|--------|------|
| `US-072` | Collect actual replacement facts | Post-Rebook Monitoring | Complete | `001-post-rebook-monitoring/stories/001-collect-actual-replacement-facts.md` |
| `US-073` | Propagate monitored replacement atomically | Post-Rebook Monitoring | Complete | `001-post-rebook-monitoring/stories/002-propagate-monitored-replacement-atomically.md` |
| `US-074` | Reconcile partial outcomes safely | Post-Rebook Monitoring | Complete | `001-post-rebook-monitoring/stories/003-reconcile-partial-outcomes-safely.md` |
| `US-075` | Preserve audit and invalidate stale savings | Post-Rebook Monitoring | Complete | `001-post-rebook-monitoring/stories/004-preserve-audit-and-invalidate-stale-savings.md` |
| `US-076` | Preserve access and visible completion | Post-Rebook Monitoring | Complete | `001-post-rebook-monitoring/stories/005-preserve-access-and-visible-completion.md` |

## 012-per-user-booking-sessions

| Unit | Stories | Status |
|------|---------|--------|
| `001-per-user-booking-sessions` | 6 stories | Complete (bolt 024) |
| `002-remote-authentication-gateway` | 6 stories | Complete (bolt 026) |

### 001-per-user-booking-sessions: Per-User Booking.com Sessions

| Story | Title | Tag | Status | File |
|-------|-------|-----|--------|------|
| `US-077` | Isolate Booking.com sessions by user | Authenticated Sessions | Complete | `001-per-user-booking-sessions/stories/001-isolate-booking-sessions-by-user.md` |
| `US-078` | Import a user session securely | Authenticated Sessions | Complete | `001-per-user-booking-sessions/stories/002-import-user-session-securely.md` |
| `US-079` | Protect user session at rest | Authenticated Sessions | Complete | `001-per-user-booking-sessions/stories/003-protect-user-session-at-rest.md` |
| `US-080` | Inspect session health safely | Authenticated Sessions | Complete | `001-per-user-booking-sessions/stories/004-inspect-session-health-safely.md` |
| `US-081` | Enforce authenticated check policy | Authenticated Sessions | Complete | `001-per-user-booking-sessions/stories/005-enforce-authenticated-check-policy.md` |
| `US-082` | Preserve session safety and lifecycle | Authenticated Sessions | Complete | `001-per-user-booking-sessions/stories/006-preserve-session-safety-and-lifecycle.md` |

### 002-remote-authentication-gateway: Remote Authentication Gateway

| Story | Title | Tag | Status | File |
|-------|-------|-----|--------|------|
| `US-089` | Request a user-bound login | Remote Authentication | Complete | `002-remote-authentication-gateway/stories/001-request-user-bound-login.md` |
| `US-090` | Verify Mini App identity and prevent replay | Remote Authentication | Complete | `002-remote-authentication-gateway/stories/002-verify-mini-app-identity.md` |
| `US-091` | Operate a transient remote mobile browser | Remote Authentication | Complete | `002-remote-authentication-gateway/stories/003-operate-transient-remote-browser.md` |
| `US-092` | Capture authenticated state and tear down | Remote Authentication | Complete | `002-remote-authentication-gateway/stories/004-capture-and-teardown-session.md` |
| `US-093` | Report outcomes and request reconnect | Remote Authentication | Complete | `002-remote-authentication-gateway/stories/005-report-and-reconnect.md` |
| `US-094` | Deploy the gateway behind HTTPS | Remote Authentication | Complete | `002-remote-authentication-gateway/stories/006-deploy-gateway-behind-https.md` |

## 013-authenticated-mobile-web-monitoring

| Unit | Stories | Status |
|------|---------|--------|
| `001-authenticated-mobile-web-monitoring` | 6 stories | Complete (bolt 025) |

### 001-authenticated-mobile-web-monitoring: Authenticated Mobile-Web Monitoring

| Story | Title | Tag | Status | File |
|-------|-------|-----|--------|------|
| `US-083` | Run every check in a configured mobile-web profile | Authenticated Mobile Web | Complete | `001-authenticated-mobile-web-monitoring/stories/001-run-checks-in-mobile-profile.md` |
| `US-084` | Bind each check to its owner's authenticated session | Authenticated Mobile Web | Complete | `001-authenticated-mobile-web-monitoring/stories/002-bind-owner-authenticated-session.md` |
| `US-085` | Fail closed when authenticated context is unverified | Authenticated Mobile Web | Complete | `001-authenticated-mobile-web-monitoring/stories/003-fail-closed-unverified-auth.md` |
| `US-086` | Preserve scripted search and bounded LLM escalation | Authenticated Mobile Web | Complete | `001-authenticated-mobile-web-monitoring/stories/004-preserve-scripted-and-llm-journey.md` |
| `US-087` | Explain every authenticated mobile-web price source | Authenticated Mobile Web | Complete | `001-authenticated-mobile-web-monitoring/stories/005-explain-price-source.md` |
| `US-088` | Keep final booking action on the user's real phone | Authenticated Mobile Web | Complete | `001-authenticated-mobile-web-monitoring/stories/006-keep-final-action-on-phone.md` |

## 014-remote-auth-display-reliability

| Unit | Stories | Status |
|------|---------|--------|
| `001-remote-auth-display-reliability` | 2 stories | Complete (bolt 027; 871 tests) |

### 001-remote-auth-display-reliability: Remote Authentication Display Reliability

| Story | Title | Tag | Status | File |
|-------|-------|-----|--------|------|
| `US-095` | Render the remote mobile-browser framebuffer | Remote Auth Reliability | Complete | `001-remote-auth-display-reliability/stories/001-render-remote-browser-framebuffer.md` |
| `US-096` | Explain remote viewer connection failures | Remote Auth Reliability | Complete | `001-remote-auth-display-reliability/stories/002-explain-viewer-connection-failures.md` |

## 015-authentication-boundary-hardening

| Unit | Stories | Status |
|------|---------|--------|
| `001-complete-user-purge` | 2 stories | Complete (bolt 028; 883 tests) |
| `002-direct-booking-auth-only` | 2 stories | Complete (bolt 029; 883 tests) |

### 001-complete-user-purge: Complete User Purge

| Story | Title | Tag | Status | File |
|-------|-------|-----|--------|------|
| `US-097` | Remove encrypted authentication state during purge | Authentication Boundary | Complete | `001-complete-user-purge/stories/001-remove-encrypted-authentication-state.md` |
| `US-098` | Prevent in-flight authentication from surviving purge | Authentication Boundary | Complete | `001-complete-user-purge/stories/002-prevent-inflight-authentication-survival.md` |

### 002-direct-booking-auth-only: Direct Booking Authentication Only

| Story | Title | Tag | Status | File |
|-------|-------|-----|--------|------|
| `US-099` | Block external identity-provider navigation | Authentication Boundary | Complete | `002-direct-booking-auth-only/stories/001-block-external-provider-navigation.md` |
| `US-100` | Guide users to direct Booking.com login | Authentication Boundary | Complete | `002-direct-booking-auth-only/stories/002-guide-direct-booking-login.md` |

## 016-device-aware-remote-auth-viewer

| Unit | Stories | Status |
|------|---------|--------|
| `001-device-aware-remote-auth-viewer` | 5 stories | Complete (bolts 030–031) |

### 001-device-aware-remote-auth-viewer: Device-Aware Remote Authentication Viewer

| Story | Title | Tag | Status | File |
|-------|-------|-----|--------|------|
| `US-101` | Present a device-adaptive streamed viewer | Remote Auth Viewer | Complete | `001-device-aware-remote-auth-viewer/stories/001-present-device-adaptive-viewer.md` |
| `US-102` | Type with the native mobile keyboard | Remote Auth Viewer | Complete | `001-device-aware-remote-auth-viewer/stories/002-type-with-native-mobile-keyboard.md` |
| `US-103` | Preserve viewport and lifecycle usability | Remote Auth Viewer | Complete | `001-device-aware-remote-auth-viewer/stories/003-preserve-viewport-and-lifecycle-usability.md` |
| `US-104` | Preserve credential and desktop safety | Remote Auth Viewer | Complete | `001-device-aware-remote-auth-viewer/stories/004-preserve-credential-and-desktop-safety.md` |
| `US-105` | Recover from an abandoned viewer | Remote Auth Viewer | Complete | `001-device-aware-remote-auth-viewer/stories/005-recover-from-abandoned-viewer.md` |

## 017-current-rebook-opportunities

| Unit | Stories | Status |
|------|---------|--------|
| `001-current-rebook-opportunities` | 3 stories | Complete (bolt 032; 909 tests) |

### 001-current-rebook-opportunities: Current Rebook Opportunities

| Story | Title | Tag | Status | File |
|-------|-------|-----|--------|------|
| `US-106` | Show one current opportunity per booking | Current Rebook | Complete | `001-current-rebook-opportunities/stories/001-show-one-current-opportunity-per-booking.md` |
| `US-107` | Reject superseded rebook selections | Current Rebook | Complete | `001-current-rebook-opportunities/stories/002-reject-superseded-rebook-selection.md` |
| `US-108` | Preserve savings audit and access boundaries | Current Rebook | Complete | `001-current-rebook-opportunities/stories/003-preserve-savings-audit-and-access-boundaries.md` |

## 018-conclusive-rebook-opportunity-lifecycle

| Unit | Stories | Status |
|------|---------|--------|
| `001-conclusive-opportunity-lifecycle` | 3 stories | Complete (bolt 033; 937 tests) |

### 001-conclusive-opportunity-lifecycle: Conclusive Opportunity Lifecycle

| Story | Title | Tag | Status | File |
|-------|-------|-----|--------|------|
| `US-109` | Preserve opportunity across technical failures | Opportunity Lifecycle | Complete | `001-conclusive-opportunity-lifecycle/stories/001-preserve-opportunity-across-technical-failures.md` |
| `US-110` | Supersede opportunity on conclusive check | Opportunity Lifecycle | Complete | `001-conclusive-opportunity-lifecycle/stories/002-supersede-opportunity-on-conclusive-check.md` |
| `US-111` | Enforce conclusive currentness atomically | Opportunity Lifecycle | Complete | `001-conclusive-opportunity-lifecycle/stories/003-enforce-conclusive-currentness-atomically.md` |

## 019-booking-account-synchronization

| Unit | Stories | Status |
|------|---------|--------|
| `001-booking-account-sync-core` | 4 stories | Complete (bolts 034–035; 959 tests) |
| `002-synchronized-booking-interface` | 3 stories | Complete (bolt 036; 959 tests) |

### 001-booking-account-sync-core: Booking Account Sync Core

| Story | Title | Tag | Status | File |
|-------|-------|-----|--------|------|
| `US-112` | Discover the complete authenticated reservation inventory | Account Synchronization | Complete | `001-booking-account-sync-core/stories/001-discover-complete-authenticated-inventory.md` |
| `US-113` | Reconcile remote reservation snapshots atomically | Account Synchronization | Complete | `001-booking-account-sync-core/stories/002-reconcile-remote-snapshots-atomically.md` |
| `US-114` | Explain eligibility and preserve price-source boundaries | Account Synchronization | Complete | `001-booking-account-sync-core/stories/003-explain-eligibility-and-price-boundary.md` |
| `US-115` | Cut over legacy state and recover from synchronization failures | Account Synchronization | Complete | `001-booking-account-sync-core/stories/004-cut-over-legacy-and-recover-failures.md` |

### 002-synchronized-booking-interface: Synchronized Booking Interface

| Story | Title | Tag | Status | File |
|-------|-------|-----|--------|------|
| `US-116` | Synchronize at every freshness boundary | Synchronized Interface | Complete | `002-synchronized-booking-interface/stories/001-synchronize-every-freshness-boundary.md` |
| `US-117` | Show future upcoming reservations and eligibility reasons | Synchronized Interface | Complete | `002-synchronized-booking-interface/stories/002-show-every-reservation-and-reason.md` |
| `US-118` | Remove manual booking mutation and guided rebooking | Synchronized Interface | Complete | `002-synchronized-booking-interface/stories/003-remove-manual-mutation-and-rebook.md` |

## 020-randomized-daily-booking-checks

| Unit | Stories | Status |
|------|---------|--------|
| `001-randomized-daily-booking-checks` | 3 stories | Complete (bolt 037; 1038 tests) |

### 001-randomized-daily-booking-checks: Randomized Daily Booking Checks

| Story | Title | Tag | Status | File |
|-------|-------|-----|--------|------|
| `US-119` | Plan durable random daily slots | Randomized Scheduling | Complete | `001-randomized-daily-booking-checks/stories/001-plan-durable-random-daily-slots.md` |
| `US-120` | Dispatch due booking checks safely | Randomized Scheduling | Complete | `001-randomized-daily-booking-checks/stories/002-dispatch-due-booking-checks-safely.md` |
| `US-121` | Configure and observe randomized scheduling | Randomized Scheduling | Complete | `001-randomized-daily-booking-checks/stories/003-configure-and-observe-randomized-scheduling.md` |

## 021-booking-browser-llm-recovery

| Unit | Stories | Status |
|------|---------|--------|
| `001-shared-booking-browser-recovery` | 4 stories | Complete (bolt 038) |
| `002-agent-assisted-booking-inventory` | 4 stories | Complete (bolts 039–040) |

### 001-shared-booking-browser-recovery: Shared Booking Browser Recovery

| Story | Title | Tag | Status | File |
|-------|-------|-----|--------|------|
| `US-122` | Detect and stop semantic no-progress | LLM Recovery | Complete | `001-shared-booking-browser-recovery/stories/001-detect-and-stop-semantic-no-progress.md` |
| `US-123` | Reorient with evidence-rich feedback | LLM Recovery | Complete | `001-shared-booking-browser-recovery/stories/002-reorient-with-evidence-rich-feedback.md` |
| `US-124` | Back every booking browser step with guarded recovery | LLM Recovery | Complete | `001-shared-booking-browser-recovery/stories/003-back-every-booking-browser-step-with-guarded-recovery.md` |
| `US-125` | Evaluate recovery with replay fixtures | LLM Recovery | Complete | `001-shared-booking-browser-recovery/stories/004-evaluate-recovery-with-replay-fixtures.md` |

### 002-agent-assisted-booking-inventory: Agent-Assisted Booking Inventory

| Story | Title | Tag | Status | File |
|-------|-------|-----|--------|------|
| `US-126` | Recover complete booking inventory discovery | Inventory Recovery | Complete | `002-agent-assisted-booking-inventory/stories/001-recover-complete-booking-inventory-discovery.md` |
| `US-127` | Preserve completeness and safety under agent assistance | Inventory Recovery | Complete | `002-agent-assisted-booking-inventory/stories/002-preserve-completeness-and-safety-under-agent-assistance.md` |
| `US-128` | Explain and observe inventory recovery | Inventory Recovery | Complete | `002-agent-assisted-booking-inventory/stories/003-explain-and-observe-inventory-recovery.md` |
| `US-129` | Recover initial inventory navigation from current evidence | Inventory Recovery | Complete | `002-agent-assisted-booking-inventory/stories/004-recover-initial-inventory-navigation-from-current-evidence.md` |

## 022-adaptive-booking-browser-resilience

| Unit | Stories | Status |
|------|---------|--------|
| `001-adaptive-model-policy` | 3 stories | Complete (bolt 041) |
| `002-dom-resilient-browser-workflows` | 4 stories | Complete (bolts 042–043) |
| `003-dom-drift-incident-operations` | 3 stories | Complete (bolt 044) |

### 001-adaptive-model-policy: Adaptive Model Policy

| Story | Title | Tag | Status | File |
|-------|-------|-----|--------|------|
| `US-130` | Escalate Sonnet to Opus on quality failure | Adaptive Resilience | Complete | `001-adaptive-model-policy/stories/001-escalate-sonnet-to-opus-on-quality-failure.md` |
| `US-131` | Enforce browser-job and daily dollar ceilings | Adaptive Resilience | Complete | `001-adaptive-model-policy/stories/002-enforce-browser-job-and-daily-dollar-ceilings.md` |
| `US-132` | Qualify adaptive model profiles | Adaptive Resilience | Complete | `001-adaptive-model-policy/stories/003-qualify-adaptive-model-profiles.md` |

### 002-dom-resilient-browser-workflows: DOM-Resilient Browser Workflows

| Story | Title | Tag | Status | File |
|-------|-------|-----|--------|------|
| `US-133` | Register every DOM-sensitive browser step | Adaptive Resilience | Complete | `002-dom-resilient-browser-workflows/stories/001-register-every-dom-sensitive-browser-step.md` |
| `US-134` | Classify the current page with LLM fallback | Adaptive Resilience | Complete | `002-dom-resilient-browser-workflows/stories/002-classify-current-page-with-llm-fallback.md` |
| `US-135` | Recover and interpret safe DOM drift | Adaptive Resilience | Complete | `002-dom-resilient-browser-workflows/stories/003-recover-and-interpret-safe-dom-drift.md` |
| `US-136` | Explain every terminal browser outcome | Adaptive Resilience | Complete | `002-dom-resilient-browser-workflows/stories/004-explain-every-terminal-browser-outcome.md` |

### 003-dom-drift-incident-operations: DOM-Drift Incident Operations

| Story | Title | Tag | Status | File |
|-------|-------|-----|--------|------|
| `US-137` | Correlate DOM-drift incidents | Adaptive Resilience | Complete | `003-dom-drift-incident-operations/stories/001-correlate-dom-drift-incidents.md` |
| `US-138` | Notify owner of maintenance required | Adaptive Resilience | Complete | `003-dom-drift-incident-operations/stories/002-notify-owner-of-maintenance-required.md` |
| `US-139` | Retain encrypted incident diagnostics | Adaptive Resilience | Complete | `003-dom-drift-incident-operations/stories/003-retain-encrypted-incident-diagnostics.md` |

## Summary

| Intent | Units | Stories | Status |
|--------|-------|---------|--------|
| `001-booksaver-agent-mvp` | 5 | 16 | MVP complete (14/14 MVP stories); Unit 5 (extensibility) is post-MVP |
| `002-agentic-search-monitor` | 2 | 6 | Complete (bolts 006–007; 345 tests) |
| `003-telegram-interface` | 5 | 14 | Complete (bolts 008–012; all 14 stories US-023–036) |
| `004-production-hardening` | 1 | 6 | Complete (bolts 013–015; 641 tests after property availability correction) |
| `005-telegram-command-navigation` | 1 | 5 | Complete (bolts 016 and 018; 668 tests) |
| `006-telegram-booking-management` | 1 | 4 | Complete (bolt 017; 696 tests) |
| `007-telegram-on-demand-checks` | 1 | 5 | Complete (bolt 019; 713 tests) |
| `008-currency-aligned-price-checks` | 1 | 5 | Complete (bolt 020; 721 tests) |
| `009-invite-first-sharing` | 1 | 5 | Complete (bolt 021; 763 tests) |
| `010-telegram-privacy-boundaries` | 1 | 5 | Complete (bolt 022; 763 tests) |
| `011-post-rebook-monitoring` | 1 | 5 | Complete (bolt 023; 788 tests) |
| `012-per-user-booking-sessions` | 2 | 12 | Complete (bolts 024 and 026; 867 tests) |
| `013-authenticated-mobile-web-monitoring` | 1 | 6 | Complete (bolt 025; 867 tests) |
| `014-remote-auth-display-reliability` | 1 | 2 | Complete (bolt 027; 871 tests) |
| `015-authentication-boundary-hardening` | 2 | 4 | Complete (bolts 028–029; 883 tests) |
| `016-device-aware-remote-auth-viewer` | 1 | 5 | Complete (bolts 030–031; 898 tests) |
| `017-current-rebook-opportunities` | 1 | 3 | Complete (bolt 032; 909 tests) |
| `018-conclusive-rebook-opportunity-lifecycle` | 1 | 3 | Complete (bolt 033; 937 tests) |
| `019-booking-account-synchronization` | 2 | 7 | Complete (bolts 034–036; 959 tests) |
| `020-randomized-daily-booking-checks` | 1 | 3 | Complete (bolt 037; 1038 tests) |
| `021-booking-browser-llm-recovery` | 2 | 8 | Complete (bolts 038–040; 1230 tests) |
| `022-adaptive-booking-browser-resilience` | 3 | 10 | Complete (bolts 041–044; 1512 tests) |

All 139 stories (137 complete in-scope stories and 2 post-MVP extensibility stories) are assigned
exactly once.
