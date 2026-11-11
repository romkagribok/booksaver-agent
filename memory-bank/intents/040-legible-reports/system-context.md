---
intent: 040-legible-reports
phase: inception
status: context-defined
created: "2026-11-11T00:10:37Z"
updated: "2026-11-11T00:10:37Z"
---

# System Context

## System Overview

- Reservation facts come from `JevReservationFacts`; `check_refund` turns Jev's class and
  sentence into refund evidence.
- Users read results through the Telegram commands (`commands_readonly.py`: `/bookings`,
  `/savings`, `/checks`; `check_now.py`: `/checknow`) and the savings alert
  (`savings_pipeline.render_alert`).

## Context Diagram

```text
Jev answers -> check_refund -> reservation (refundable, note, deadline) -> /bookings
check history / savings -> plain-language formatter -> /checks, /checknow, /savings, alert
```

## External Integrations

TypeSafe Jev (unchanged questions), Telegram (reply text only).
