---
stage: plan
bolt: 032-current-rebook-opportunities
created: 2026-07-27T02:14:27Z
---

## Implementation Plan: Current Rebook Opportunities

### Objective

Make the newest known savings result the only guided-rebook action for each active booking while
retaining historical results for audit and rejecting old Telegram buttons or manual identifiers.

### Deliverables

- A persistence port and SQLite implementation for resolving the newest opportunity for one booking.
- A one-query SQLite listing that returns one newest opportunity per active booking owned by a user.
- Telegram picker wiring that consumes only current choices.
- Telegram preflight and shared application-service freshness guards.
- Clear stale-selection guidance that creates no session or confirmation prompt.
- Integration, service, Telegram, and scoping regression tests.

### Dependencies

- Existing append-only `savings_opportunities` persistence and booking ownership.
- Existing `/rebook` callback flow and `RebookSessionService`.
- Existing ADR-023 audit-history versus stale-action boundary.

### Technical Approach

1. Extend the savings repository contract with explicit current-opportunity operations rather than
   assigning an undocumented ordering meaning to historical list methods.
2. Resolve the newest row with `(validated_at DESC, id DESC)`, where the SQLite insertion ID is the
   deterministic tie-breaker.
3. Use a correlated `NOT EXISTS` subquery joined to active owned bookings to return one current row
   per booking in one query without requiring SQLite window functions.
4. Keep `list_all`, `list_all_for_user`, and `list_for_booking` historical and unchanged for audit
   readers.
5. Add a distinct superseded-opportunity application error. `RebookSessionService` performs an
   optimistic check, then the SQLite session repository validates currentness and inserts the
   session inside one immediate transaction.
6. Telegram checks the same condition before allocating a worker so stale callbacks receive
   immediate `/rebook` guidance; the application guard remains authoritative against races and CLI
   callers.
7. Preserve all existing ownership, active-session, callback acknowledgement, confirmation, and
   human final-action behavior.

### Acceptance Criteria

- [ ] One active booking with many opportunities renders one newest choice.
- [ ] Multiple active bookings render one newest choice each in global newest-first order.
- [ ] Same-time opportunities resolve by SQLite insertion order.
- [ ] Archived and foreign-owned bookings do not render.
- [ ] Superseded direct commands and callbacks create no session or prompt.
- [ ] The application service rejects a stale ID before persisting a session.
- [ ] Historical savings readers retain every stored row.
- [ ] Focused and full repository quality gates pass.

### Risks and Controls

- **Stale rendered callback**: repeat freshness validation when starting and in the service.
- **Picker/service race**: currentness validation and session creation share one immediate
  transaction.
- **History loss**: add no delete/update operation and explicitly test historical listing.
- **Ownership regression**: select through the booking owner and retain existing non-enumerating
  command checks.
- **Timestamp tie**: use persistence insertion ID as a stable secondary order.
