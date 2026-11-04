---
unit: 001-jev-reservation-reader
intent: 030-jev-only-booksaver
phase: inception
status: in-progress
unit_type: backend
default_bolt_type: ddd-construction-bolt
created: "2026-11-04T15:34:52Z"
updated: "2026-11-04T15:34:52Z"
---

# Unit Brief: Jev reservation reader

## Purpose and scope

Make Jev the only reader of booked totals and refund terms during sync.

## Assigned requirements

FR-1 to FR-6. See ../../requirements.md.

## Stories

| Story | Title | Bolt |
|---|---|---|
| US-243 | Read totals and refund terms with Jev alone | 098-jev-reservation-reader |
| US-244 | Remove the code price and refund parsing | 098-jev-reservation-reader |
| US-245 | Keep failures visible without notices | 098-jev-reservation-reader |
