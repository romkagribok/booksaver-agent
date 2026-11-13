---
intent: 041-desktop-price-trial
phase: construction
status: construction
created: "2026-11-13T03:02:27Z"
updated: "2026-11-13T03:02:27Z"
---

# Requirements: One-week silent desktop price trial

## Intent Overview

GitHub issue #7 proposes checking every booking on both the mobile and the desktop Booking.com
site and alerting on the cheaper valid offer. Before building that, the owner wants to know
whether a desktop reading is ever cheaper. Owner, 2026-11-12: "We need to run a trial on my
fathers booking without him necessary seeing because he has a lot of them so we will get more
data. Let's see if it's worth it. If over the course of the week, the readings don't matter much,
we can retire this and close the issue".

This intent adds a silent desktop reading beside the normal mobile check for the users named in
config (user 4 in production), stores the pairs, and stops by itself after the trial's end date.
Nothing a user can see changes. The rest of issue #7 is out of scope until the trial is judged.

## Business Goals

| Goal | Success Metric | Priority |
|------|----------------|----------|
| Know whether desktop prices matter | A week of paired mobile and desktop readings for user 4's bookings | Must |
| The trial user notices nothing | No message, history row, alert or check limit changes because of the trial | Must |
| Cheap to remove | The trial is one config section, one table and code that names the trial | Should |

---

## Functional Requirements

### FR-1: Desktop browser profile
- **Description**: A code-owned desktop Chromium profile (Playwright's "Desktop Chrome") that the
  Jev browser host can run: desktop viewport, no touch or mobile emulation, desktop platform. It
  cannot be selected through `[browser] device_profile`.
- **Acceptance Criteria**: The desktop profile produces context options with `is_mobile` and
  `has_touch` false; `[browser] device_profile = "desktop-chromium"` is rejected; the mobile
  profiles and their validation are unchanged.
- **Priority**: Must
- **Related Stories**: US-268

### FR-2: Read the desktop room table
- **Description**: The page reader reads Booking.com's desktop room table, where one room cell
  spans several rate rows: each row is a rate of the room whose cell spans it; the price is read
  from the row's price cell even though Booking.com marks it hidden from screen readers; amounts
  outside the price cell (paid breakfast, the room-count selector) are not offered as totals; a
  row that states fewer guests than the search is skipped.
- **Acceptance Criteria**: On a saved desktop table with two rooms of two rates each, the reader
  returns two rooms with their names and two rates each, each rate holding its whole-stay price
  line and its cancellation line and no selector or paid-breakfast amount; the mobile card
  reading returns the same result as before for the existing fixtures.
- **Priority**: Must
- **Related Stories**: US-268

### FR-3: Silent desktop reading after a scheduled slot
- **Description**: For a user listed in `[desktop_trial] user_ids`, before `ends_on`, a
  scheduled slot takes one desktop reading for each booking it checked, after all of that slot's
  normal checks. The reading goes through the same validators and offer selection as the mobile
  check and is stored with the mobile check's id.
- **Acceptance Criteria**: A slot for a trial user stores one reading per checked booking with
  outcome, price, currency, offered room and failure reason; a slot for any other user, or on or
  after `ends_on`, stores none; `/checknow` takes no desktop reading.
- **Priority**: Must
- **Related Stories**: US-269

### FR-4: The trial changes nothing the user can see or rely on
- **Description**: A desktop reading writes no check history, check trace, savings opportunity or
  alert, sends no message, does not count as a check, never writes the saved session, runs on its
  own time limit after the slot's checks, and never raises into the slot. Its Jev spend is
  recorded under its own adapter name and it stops once the user's spend for the day passes half
  the daily cap. The slot's remaining readings are skipped when one ends signed out or at a bot
  wall.
- **Acceptance Criteria**: After a trial slot, check history, traces, savings and the daily check
  counter equal those of the same slot without the trial; the saved session revision is
  unchanged by the desktop reading; an exception in a reading is logged and the slot completes.
- **Priority**: Must
- **Related Stories**: US-269

### FR-5: Evaluate after a week, then keep or retire
- **Description**: After `ends_on` the stored pairs are summarised: pairs taken, pairs where
  both sides verified a price, pairs where desktop was cheaper by at least the alert minimum (5 in
  the booking currency), and desktop failure reasons. The owner decides. If desktop does not
  matter, a follow-up bolt removes the trial and issue #7 is closed.
- **Acceptance Criteria**: The summary and the owner's decision are recorded in the release
  record; no report command is built (one SQL query, run by the operator).
- **Priority**: Must
- **Related Stories**: US-269 (data); the evaluation is an operations step

---

## Non-Functional Requirements

### Security
| Requirement | Standard | Notes |
|-------------|----------|-------|
| Per-user data boundary | AGENTS.md | Readings are deleted with their booking or user |
| Session isolation | ADR-025 | The reading uses only the booking owner's session and never writes it back |
| Stored content | AGENTS.md | A reading stores outcome, price, room label and the failure reason; no page text |

### Reliability
| Requirement | Metric | Target |
|-------------|--------|--------|
| Normal checks unaffected | Mobile check results, time budget, counters | Identical with and without the trial |
| Bounded | Readings per slot, seconds per reading | One per checked booking, 120 seconds each |
| Ends by itself | Readings on or after `ends_on` | None |

### Performance
| Requirement | Metric | Target |
|-------------|--------|--------|
| Booking.com traffic | Extra property page loads | One reading per checked booking per slot, trial users only |
| Jev spend | Share of the user's daily cap | At most half |

---

## Constraints

### Technical Constraints

**Project-wide standards**: loaded from the memory-bank standards folder by Construction.

**Intent-specific constraints**:
- ADR-021: one coordinator, one browser at a time. Readings run inside the slot's execution gate,
  so other browser work waits or is refused as busy while they run.
- ADR-025 stays: mobile web is the only price source that produces results, savings and alerts.
- The desktop page can only be tuned against real pages. The reader was prototyped on public
  desktop pages on 2026-11-12; signed-in behaviour is qualified on the VPS before user 4 is enabled.

### Business Constraints
- Owner decision in the request; standing waiver for human checkpoints (CLAUDE.local.md point 4).
- The trial user is not told and must not notice.

---

## Assumptions

| Assumption | Risk if Invalid | Mitigation |
|------------|-----------------|------------|
| Booking.com accepts the saved session from a desktop profile | It signs the session out or asks for verification, which would also break the user's mobile checks | Qualify on the owner's own session first; the reading never writes cookies; readings stop for the slot at a sign-out; `user_ids = []` turns the trial off |
| The signed-in desktop page uses the room table seen on public pages | Readings fail closed and the trial yields no pairs | Live qualification before enabling; failure reasons are stored |
| Twice the page loads for one user does not trigger the edge block | The VPS IP is refused for every user | Readings stop for the slot at a bot wall; trial limited to one user and one week |

---

## Open Questions

| Question | Owner | Due Date | Resolution |
|----------|-------|----------|------------|
| Does a desktop profile keep the mobile session valid? | Engineering | Before enabling user 4 | Live qualification on the owner's session |
| Does desktop ever beat mobile by 5 or more? | Owner | After `ends_on` | The trial's result |
