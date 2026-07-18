# System Architecture Standards

## Architecture Style

Use a single-process, local-first daemon architecture. Keep components modular inside one Python application rather than introducing distributed services.

```mermaid
flowchart TB
    Config["LocalConfig (+ agent caps)"] --> Scheduler["Scheduler"]
    Scheduler --> Monitor["BookingComSearchMonitor"]
    Monitor --> Journey["SearchJourney (trusted results query → verified property)"]
    Journey --> Browser["BrowserAutomation"]
    Journey -- "step failed" --> Agent["BrowserAgent (LLM, guarded)"]
    Agent --> Browser
    Monitor --> LLM["LLMClient (offer extraction + agent brain)"]
    Monitor --> Store["LocalPersistence (+ check traces)"]
    Store --> Savings["SavingsDetection"]
    Savings --> Notify["Notifications"]
    Savings --> Rebook["GuidedRebook"]
    Rebook --> Browser
    Rebook --> Store
```

## Boundaries

- Booking.com integration happens through browser automation only. Live prices come from a trusted
  results query followed by exact property selection, fresh property navigation, context verification,
  and room-rate extraction (ADR-013 amended by ADR-020); the homepage form, manage page, registered-
  property deep link, and result-card headline price are not price sources.
- The LLM is used for extraction and reasoning when DOM parsing is insufficient, and as a
  guarded browser agent when a scripted journey step fails (ADR-015/016): bounded action
  vocabulary, adapter-level denylist against reserve/checkout/payment/cancel, hard
  per-check cost caps (ADR-017).
- Notification adapters send directly through the user's configured services.
- Guided rebook must never execute cancel or purchase actions without explicit local confirmation.
- All secrets, sessions, booking data, logs, and check history remain on the user's machine.

## Unit Build Order

1. Core & Local Data
2. Booking.com Price Monitor
3. Savings Detection & Notifications
4. Guided Rebook
5. Extensibility (future only)
