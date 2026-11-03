---
intent: 029-jev-reservation-facts
phase: inception
status: context-defined
created: "2026-11-03T19:24:37Z"
updated: "2026-11-03T19:24:37Z"
---

# Jev-assisted reservation facts - System Context

## System Overview

The grouped inventory reader already parses each confirmation page with code. When that leaves the
total or refund terms unknown, the same component builds candidate lines and asks Jev through the
existing `MeteredJevDecider` and TypeSafe client. Code proves the pick and returns the fact as if
the code reader had read it.

## Context Diagram

```text
confirmation page -> code reader -> unknown total/refund -> candidate lines -> Jev (TypeSafe)
     -> pick -> code proof -> fact (page-verified) -> reconciliation (ADR-058, ADR-059)
```

## External Integrations

TypeSafe, already used by price checks. No new dependency.
