---
intent: 013-authenticated-mobile-web-monitoring
phase: inception
status: complete
created: 2026-07-19T21:23:00Z
updated: 2026-07-19T21:23:00Z
---

# System Context: Authenticated Mobile-Web Monitoring

## Actors and Systems

- **Telegram user**: Owns the booking/session and receives provenance-labeled outcomes.
- **Check coordinator**: Serializes scheduled and on-demand work.
- **Per-user session provider**: Supplies exactly one authenticated owner revision.
- **Playwright Chromium**: Emulates the configured mobile-web device.
- **Booking.com mobile website**: Renders authenticated/account/mobile-eligible offers.
- **LLM browser/extraction adapters**: Recover or interpret ambiguous mobile layouts within existing guards.

```mermaid
flowchart LR
    Trigger["Scheduler or /checknow"] --> Owner["Resolve booking owner"]
    Owner --> Session["Intent 012 session revision"]
    Session --> Mobile["Fresh mobile Chromium context"]
    Mobile --> Journey["Trusted search + exact property journey"]
    Journey --> Verify["Auth + Genius evidence + context verification"]
    Verify --> Price["Equivalent refundable final total"]
    Price --> Provenance["Durable price-source provenance"]
    Provenance --> Alert["History / alert / Telegram result"]
    Journey -. "bounded recovery" .-> LLM["Guarded LLM agent"]
```

## Trust Boundary

The session revision is opaque outside Intent 012. Mobile monitoring may restore state and report a
revision identifier/validation result but cannot persist or log raw browser state.
