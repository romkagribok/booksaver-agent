---
unit: 003-delete-claude-code
bolt: 100-delete-claude-code
stage: model
status: complete
created: 2026-11-06T01:24:25Z
updated: 2026-11-06T01:24:25Z
---

# Static Model - Delete the Claude Code

## Bounded Context

The whole source tree. Behaviour after release A is the contract: Jev price checks for every user
through `BookingComSearchMonitor`'s agentic branch, account sync through the grouped reader with
Jev facts, Telegram, remote login and session maintenance unchanged.

## Domain Rules

1. Nothing that runs in production changes behaviour; only code that cannot run is removed.
2. Shared helpers keep their behaviour when moved.
3. The DOM-incident model (including `UsdAmount` and the attempt enums) stays.
