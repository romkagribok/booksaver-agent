# System Architecture Standards

## Architecture Style

Use a single-process, local-first daemon architecture. Keep components modular inside one Python application rather than introducing distributed services.

```mermaid
flowchart TB
    Config["LocalConfig (+ agent caps)"] --> Coordinator["CheckCoordinator"]
    Scheduler["Scheduler"] --> Coordinator
    Telegram["Telegram /checknow"] --> Coordinator
    Telegram --> Connect["Telegram /connect"]
    Connect --> AuthGateway["HTTPS Mini App gateway"]
    AuthGateway --> LoginBrowser["Transient headed mobile browser"]
    LoginBrowser --> SessionVault["Encrypted per-user session vault"]
    SessionVault --> Inventory["Booking.com Account Inventory"]
    Inventory --> Store["LocalPersistence (+ sync audit/check traces)"]
    Coordinator --> Monitor["BookingComSearchMonitor"]
    SessionVault --> Monitor
    Monitor --> PricePort["PriceBrowserExecutor"]
    PricePort --> BrowserUse["Browser Use (default agentic)"]
    PricePort --> Stagehand["Stagehand (explicit rollback)"]
    BrowserUse --> Validation["BookSaver validation/equivalence"]
    Stagehand --> Validation
    Monitor --> Journey["SearchJourney (trusted results query → verified property)"]
    Journey --> Browser["BrowserAutomation"]
    Journey -- "step failed" --> Agent["BrowserAgent (LLM, guarded)"]
    Agent --> Browser
    Monitor --> LLM["LLMClient (offer extraction + agent brain)"]
    Monitor --> Store
    Store --> Savings["SavingsDetection"]
    Savings --> Notify["Notifications"]
```

## Boundaries

- Booking.com integration happens through browser automation only. Live prices come from a trusted
  results query followed by exact property selection, fresh property navigation, context verification,
  availability/rate readiness, and room-rate extraction (ADR-013 amended by ADR-020); property loading
  does not depend on a legacy room-table selector, and the homepage form, manage page, registered-
  property deep link, and result-card headline price are not price sources.
- The LLM is used for extraction and reasoning when DOM parsing is insufficient, and as a
  guarded browser agent when a scripted journey step fails (ADR-015/016): bounded action
  vocabulary, adapter-level denylist against reserve/checkout/payment/cancel, hard
  per-check cost caps (ADR-017).
- Scheduled and Telegram-triggered live checks enter one daemon-lifetime coordinator. It serializes
  Playwright work, shares per-user daily check/actual-LLM counters, and reuses the complete monitor,
  trace, savings, and notification pipeline (ADR-021); do not add a second scheduler or browser path.
- The agentic price route selects one replaceable adapter behind `PriceBrowserExecutor`. Browser Use
  is the default for both manual and scheduled jobs; Stagehand is an explicit future-job rollback.
  Both restore the owner session only through local CDP and return untrusted typed evidence.
  BookSaver alone verifies query identity, dates, occupancy, authentication, currency, all-in total,
  refundability, equivalence, and savings. Never chain adapters within one job (ADR-043).
- Telegram-owned checks resolve the booking owner's encrypted session and create a fresh Android
  Chromium mobile-web context; missing, stale, rendered-signed-out, or mismatched state fails closed
  as `auth_required` (ADRs 024–025). Never substitute a global, public, or another user's session.
- The authenticated Booking.com account inventory is authoritative for reservation facts and
  lifecycle (ADRs 027–028). Synchronize after `/connect`, before checks, and when `/bookings` is
  requested; preserve unseen reservations unless a complete traversal proves absence. Persist every
  visible reservation and derive monitorable booking projections only for reason-coded eligible rows.
- The opt-in `/connect` adapter is the narrow exception to outbound-only operation (ADR-026). A
  signed Telegram Mini App reaches a stdlib HTTP gateway behind Caddy TLS, drives one transient
  headed mobile browser through token-gated noVNC/websockify, and treats that page only as a cookie
  producer. A versioned isolated Booking server contract accepts exact negative controls—including
  the cookie-free edge-pending tuple—without closing the viewer, and captures cookies only after two
  exact positive probes issue a receipt bound to the immutable snapshot (ADR-035). It then tears
  down. The flow shares the same global browser lease as checks. No endpoint accepts credentials,
  cookie JSON, arbitrary URLs, uploads, or free-form browser actions.
- The remote login browser runs on the trusted self-hosted VPS. HTTPS and encryption do not protect
  keystrokes against compromised VPS root; stronger disposable/device-local isolation is future
  hardening, not a security property of the current design.
- Notification adapters send directly through the user's configured services.
- Savings notifications are informational. BookSaver does not create or guide a rebooking workflow;
  users manage reservations directly in Booking.com and later synchronization observes the result.
- All secrets, sessions, booking data, logs, and check history remain on the user's machine.

## Unit Build Order

1. Core & Local Data
2. Booking.com Account Synchronization
3. Booking.com Price Monitor
4. Savings Detection & Notifications
5. Extensibility (future only)
