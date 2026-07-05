---
unit: 002-booking-com-price-monitor
bolt: 003-booking-com-price-monitor
stage: model
status: complete
updated: 2026-07-05T00:00:00Z
---

# Domain Model — Booking.com Price Monitor

> Scope: Bolt `003-booking-com-price-monitor` — **US-004** (session), **US-005** (scheduled
> browser check), **US-006** (LLM extraction), **US-014** (failure handling).
> Builds on Config, Booking, BookingRepository, and Scheduler from Unit 1.
> No source code is produced in this stage.

## Bounded Context

**Booking.com Price Monitor** is the browser automation and extraction context. It owns:

1. **Session state** — Booking.com authentication cookies, persisted locally, reused across
   ticks until expiry.
2. **Check execution** — navigating to each active booking's manage page on schedule,
   extracting the live price and refund indicators.
3. **Check history** — every run's outcome (success or failure) recorded in local storage.

This context is a **consumer** of Core & Local Data (reads `Booking` records, `Config`,
uses the `Scheduler` hook). It **produces** `CheckResult` records that Unit 3
(Savings Detection) will consume. Browser automation, LLM extraction, and failure logging
are internal to this context — Units 3 and 4 never call Playwright or the LLM directly.

## Domain Entities

| Entity | Properties | Business Rules |
|--------|------------|----------------|
| **CheckResult** (aggregate root) | `checkId`, `bookingId`, `checkedAt`, `outcome` (`success`/`failure`), `livePrice` (Money, nullable), `refundIndicators` (extracted flags), `extractedProperty`, `extractedRoomType`, `extractedDates`, `failureReason` (nullable), `extractionMethod` (`dom`/`llm`/`none`) | `livePrice` must be present when `outcome = success`; `failureReason` must be present when `outcome = failure`; `bookingId` must reference a registered booking; a check record is immutable once written |
| **SessionState** | `sessionId`, `platform` (`booking_com`), `cookies` (serialised, opaque), `authenticatedAt`, `expiresAt` (nullable), `status` (`active`/`expired`/`requires_reauth`) | Cookies are never logged or sent outside the local machine; `status` transitions: `active → expired` on expiry, `active/expired → requires_reauth` on auth failure; only one active session per platform |

## Value Objects

| Value Object | Properties | Constraints |
|--------------|------------|-------------|
| **CheckOutcome** | enum: `success`, `failure` | Immutable per check record |
| **ExtractionMethod** | enum: `dom`, `llm`, `none` | Records how price was obtained; `none` only valid on failure |
| **RefundIndicators** | `isRefundable` (bool), `cancellationDeadline` (date, nullable), `rawText` (string, nullable) | Extracted best-effort; `rawText` preserves the original page text for audit |
| **ExtractedBookingFields** | `propertyName` (nullable), `roomLabel` (nullable), `checkIn` (date, nullable), `checkOut` (date, nullable) | All nullable — extraction may be partial; used by Unit 3 for equivalence checks |
| **SessionStatus** | enum: `active`, `expired`, `requires_reauth` | Drives whether daemon attempts a check or skips and alerts |
| **FailureReason** | `code` (enum: `navigation_error`, `auth_required`, `extraction_failed`, `llm_error`, `timeout`, `unknown`), `detail` (string) | Structured for logging and threshold counting |
| **FailureThreshold** | `maxConsecutiveFailures` (int) | From config; when reached, a local warning is emitted; default 3 |

## Aggregates

| Aggregate Root | Members | Invariants |
|----------------|---------|------------|
| **CheckResult** | `CheckOutcome`, `ExtractionMethod`, `RefundIndicators`, `ExtractedBookingFields`, `FailureReason` | Immutable once written; `livePrice` ↔ `outcome` consistency; references a valid `bookingId` |
| **SessionState** | `SessionStatus`, cookies (opaque blob) | Single active session per platform; cookies never leave the local machine |

## Domain Events

| Event | Trigger | Payload |
|-------|---------|---------|
| **CheckSucceeded** | Browser check extracts a valid live price | `checkId`, `bookingId`, `livePrice`, `currency`, `refundIndicators`, `extractedFields`, `extractionMethod`, `checkedAt` |
| **CheckFailed** | Any failure (navigation, auth, extraction, LLM, timeout) | `checkId`, `bookingId`, `failureReason`, `checkedAt` |
| **SessionExpired** | Session status transitions to `expired` | `sessionId`, `platform`, `expiredAt` |
| **ReauthRequired** | Session status transitions to `requires_reauth` | `sessionId`, `platform`, `reason` |
| **RepeatedFailureWarning** | Consecutive failure count reaches threshold | `bookingId`, `consecutiveFailures`, `threshold`, `lastFailureReason` |

## Domain Services

| Service | Operations | Dependencies |
|---------|------------|--------------|
| **BookingComMonitor** | `run_check(booking: Booking) -> CheckResult` — opens the booking's manage page, extracts live price (DOM first, LLM fallback), builds `CheckResult`, persists it; emits `CheckSucceeded` or `CheckFailed` | `BrowserSession` port, `LLMExtractor` port, `CheckHistoryRepository` |
| **SessionManager** | `ensure_active() -> SessionState` — loads session, checks expiry, triggers reauth if needed; `save(session: SessionState) -> void` | `SessionRepository` port, `BrowserSession` port |
| **FailureTracker** | `record_failure(bookingId, reason) -> int` — increments consecutive failure count, returns new count; `reset(bookingId) -> void` — resets on success; `check_threshold(bookingId) -> bool` — returns True if threshold reached | `CheckHistoryRepository` |

## Repository / Port Interfaces (new)

| Port | Operations | Notes |
|------|------------|-------|
| **CheckHistoryRepository** | `add(result: CheckResult) -> void`, `get_recent(bookingId, limit) -> list[CheckResult]`, `count_consecutive_failures(bookingId) -> int` | Finalises the stub created in Bolt 001's `check_history` table |
| **SessionRepository** | `load(platform) -> SessionState \| None`, `save(session: SessionState) -> void` | Persists opaque cookie blob to a local file (not SQLite — browser-native format) |
| **BrowserSession** (port) | `open_page(url: str) -> PageContent`, `get_cookies() -> bytes`, `restore_cookies(data: bytes) -> void`, `is_authenticated() -> bool` | Implemented by Playwright adapter; never touches a BookSaver cloud endpoint |
| **LLMExtractor** (port) | `extract_price(page_text: str, booking: Booking) -> ExtractionResult` | Implemented by Anthropic SDK adapter; API key from local config only |

## Ubiquitous Language Additions

| Term | Meaning |
|------|---------|
| **Check** | One scheduled run against one booking — opens the page, extracts, records outcome |
| **CheckResult** | The immutable local record of what a single check found or why it failed |
| **Session** | Booking.com authentication state (cookies) stored locally and reused across ticks |
| **Reauth** | The process of re-logging into Booking.com when the session has expired |
| **DOM extraction** | Parsing the page HTML directly with CSS/XPath selectors — fast, fragile to layout changes |
| **LLM extraction** | Sending page text to the configured LLM API to parse price and policy fields — robust but slower and costs API credits |
| **Consecutive failures** | Count of back-to-back failed checks for one booking; triggers a warning at threshold |
| **PageContent** | Raw HTML + optional screenshot returned by the browser session port |

## Forward References

- Unit 3 (`003-savings-detection-notifications`) reads `CheckResult` records via `CheckHistoryRepository`
  to compare `livePrice` against the booking's `baselinePrice`.
- Unit 4 (`004-guided-rebook`) reuses the `BrowserSession` port for the rebook automation flow.
- `check_history` table columns are finalised in this bolt's Stage 2 (Technical Design).
