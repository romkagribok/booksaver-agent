---
stage: implement
bolt: 112-minimum-saving
created: 2026-11-10T14:54:13Z
---

# Implementation Walkthrough: minimum-saving

## Summary

`detect_savings` rejects a saving below `MINIMUM_SAVING` (5) of the booking currency with
`RejectionReason.SAVING_BELOW_MINIMUM`, after the equivalence, currency and lower-price checks.

## Structure Overview

`src/booksaver/domain/savings.py` only; the pipeline already logs and skips any rejection.

## Completed Work

- Constant, rejection value, one comparison.

## Key Decisions

Domain rule rather than configuration: one owner-chosen value, every alert path uses it.

## Deviations from Plan

None.

## Dependencies Added

None.

## Developer Notes

Human checkpoints skipped under the standing waiver (CLAUDE.local.md point 4).
