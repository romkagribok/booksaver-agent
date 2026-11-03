---
unit: 001-reservation-change-sync
intent: 028-reservation-change-reconciliation
phase: inception
status: complete
unit_type: backend
default_bolt_type: ddd-construction-bolt
created: "2026-11-02T20:51:19Z"
updated: "2026-11-02T20:51:19Z"
---

# Unit Brief: Reservation change sync

## Purpose and scope

Code-read stay facts, stale fact clearing, informational conversion line, hold.

## Assigned requirements

FR-1, FR-2, FR-3, FR-4, FR-5. See ../../requirements.md.

## Stories

| Story | Title | Bolt |
|---|---|---|
| US-233 | Accept code-read reservation changes | 093-reservation-change-sync |
| US-234 | Clear stale facts and hold | 093-reservation-change-sync |
| US-235 | Read the total under a conversion line | 093-reservation-change-sync |
