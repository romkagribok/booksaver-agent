---
id: 006-handle-property-availability-page
unit: 001-production-reliability
intent: 004-production-hardening
status: complete
priority: must
created: 2026-07-18T20:00:27.000Z
assigned_bolt: 015-production-reliability
implemented: true
---

# Story: Handle Property Availability Page

**Global story ID**: US-042

## User Story

**As a** Telegram user monitoring a registered booking
**I want** BookSaver to distinguish a loaded property page from its availability/rate content
**So that** consent overlays, missing URL context, legitimate no-availability pages, and room-layout
drift do not turn into six-minute blind click loops

## Acceptance Criteria

- [ ] **Given** an exact result-card property href, **When** BookSaver opens it, **Then** trusted
  check-in, check-out, adult, child, and room parameters are merged into that fresh href without using
  the registered property URL.
- [ ] **Given** a Booking.com consent panel appears after results or property navigation, **When** the
  journey continues, **Then** it dismisses the panel read-only, preferring decline/reject and using
  accept only as a fallback.
- [ ] **Given** the correct property page loads without a legacy room-table selector, **When**
  `open_property` completes, **Then** it does not require rate content before the following context
  verification step.
- [ ] **Given** property context is evaluated, **When** any date or occupancy parameter is missing or
  wrong, **Then** the check fails before offer extraction.
- [ ] **Given** a room table uses a known selector or semantically recognizable room/rate text,
  **When** `read_room_table` runs, **Then** the journey proceeds to the existing DOM/LLM offer
  extraction pipeline.
- [ ] **Given** room/rate content is not yet present, **When** the step escalates, **Then** the guarded
  LLM receives a screenshot-first, step-specific goal and may perform only existing read-only actions.
- [ ] **Given** Booking.com explicitly reports no availability or sold-out inventory, **When** the
  page is interpreted, **Then** the check ends promptly as `NO_EQUIVALENT_OFFER`, not as a timeout.
- [ ] **Given** a bot wall, wrong property context, destructive action, or exhausted budget, **When**
  recovery runs, **Then** existing fail-closed behavior remains authoritative.

## Technical Notes

- Preserve ADR-020's results-query → fresh result href → verified property flow.
- Reorder responsibilities inside the existing named steps; do not add a new provider or scraping
  path.
- Use deterministic consent dismissal because it is a privacy/control surface, not a price-layout
  interpretation problem.
- Keep offer extraction in `SearchCheckJob`; journey readiness may use conservative text evidence but
  may never produce a price itself.

## Dependencies

### Requires

- US-041 / bolt 014 query-driven search entry.
- US-019 offer extraction and selection.
- US-020 through US-022 guarded LLM recovery, budgets, traces, and snapshots.

### Enables

- A VPS smoke test that reaches either a verified offer or an explicit availability outcome.

## Edge Cases

| Scenario | Expected Behavior |
|----------|-------------------|
| Fresh href already has conflicting dates | Persisted booking values overwrite only search-context parameters |
| Consent panel is absent | Dismissal is a no-op |
| Known room-table selector changes | Semantic room/rate evidence or guarded LLM recovery can satisfy readiness |
| Page says “no rooms available” | Fail promptly with `NO_EQUIVALENT_OFFER` |
| Generic property page has no rates and no explicit availability outcome | Bounded LLM recovery, then a coded failure |

## Out of Scope

- Treating search-card prices as savings evidence.
- Direct navigation to the originally registered property URL.
- Autonomous reserve, checkout, payment, cancellation, or purchase.
- Raising hard agent budgets.
