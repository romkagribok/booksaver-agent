---
intent: 039-minimum-saving
phase: inception
status: context-defined
created: "2026-11-10T14:50:41Z"
updated: "2026-11-10T14:50:41Z"
---

# System Context

## System Overview

`SavingsPipeline.process` calls `detect_savings` for each successful check; an opportunity is
stored and alerted only when it returns one. The minimum is checked there.

## Context Diagram

```text
successful check -> detect_savings (equivalence, currency, lower price, saving >= 5) -> store + alert
```

## External Integrations

None.
