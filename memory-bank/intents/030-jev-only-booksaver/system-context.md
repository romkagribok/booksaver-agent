---
intent: 030-jev-only-booksaver
phase: inception
status: context-defined
created: "2026-11-04T15:34:52Z"
updated: "2026-11-04T15:34:52Z"
---

# Jev-only BookSaver - System Context

## System Overview

Unit 1: the grouped inventory reader parses identity, dates, room, guests and meal plan with code,
then Jev reads the total and refund terms through the existing TypeSafe client and spend cap.

## Context Diagram

```text
confirmation page -> code reader (identity, stay, room, guests, meals)
                  -> Jev x2 (total, refund class, deadline line) -> checks -> facts -> reconciliation
```

## External Integrations

TypeSafe only (unchanged).
