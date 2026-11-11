---
intent: 040-legible-reports
phase: construction
status: construction
created: "2026-11-11T00:10:37Z"
updated: "2026-11-11T00:10:37Z"
---

# Requirements: Accurate, legible reports for users

## Intent Overview

On 2026-11-10 one of user 4's booking pages (Aloft, check-in 2026-11-11) counted as "cancellation
terms not read" on every sync. Its free-cancellation date had already passed, and the code dropped
the term instead of recording that free cancellation had ended. Reviewing what users see also showed
internal IDs, raw timestamps, failure codes cut off mid-sentence and browser-profile names in
`/savings`, `/checks`, `/checknow` and the savings alert. Owner (2026-11-11): "yeah create a
small fix so that all the reports that the user see are accurate and legible".

## Business Goals

| Goal | Success Metric | Priority |
|------|----------------|----------|
| Cancellation terms are read on every page | A passed free-cancellation date is recorded as ended, not unread | Must |
| Users understand every report | No internal ID, failure code or browser profile in user replies | Must |

---

## Functional Requirements

### FR-1: A passed free-cancellation date is read as "free cancellation ended"
- **Description**: When Jev reads a free-cancellation-until-a-date term whose date has passed,
  the reservation is recorded as not refundable, with the note "Free cancellation ended on
  <date>." It no longer counts as unread.
- **Acceptance Criteria**: A passed deadline gives explicit non-refundable evidence with that note.
  A future deadline is unchanged. A deadline after check-in is still unread.
- **Priority**: Must
- **Related Stories**: US-265

### FR-2: `/bookings` and `/savings` are legible
- **Description**:
  - `/bookings` shows stay dates as "12 – 15 Nov 2026" and adds "Free cancellation until
    <date>" when one is known. The reasons read "no free cancellation" and "cancellation terms
    unknown".
  - `/savings` lists each saving by hotel and stay: what was paid, the price found, the saving and
    when it was found. No IDs.
- **Acceptance Criteria**: The rendered replies contain no UUID prefixes and no ISO timestamps.
- **Priority**: Must
- **Related Stories**: US-266

### FR-3: `/checks`, `/checknow` and the alert speak plainly
- **Description**:
  - `/checks` names the hotel, stay and price paid. Each check reads "10 Nov, 18:54 UTC: 144 USD,
    3.78 USD below what you paid", or a plain reason such as "no rooms available for your dates".
  - `/checknow` uses the same wording, plus the 5-unit alert minimum when the saving is smaller.
  - The alert says "Checked as: signed in to your Booking.com account", and "Genius prices were
    shown" when they were, instead of the browser profile.
- **Acceptance Criteria**: No failure code, check ID or browser profile appears in these replies.
  Every failure code has a plain sentence, with a generic fallback.
- **Priority**: Must
- **Related Stories**: US-267

---

## Non-Functional Requirements

| Requirement | Metric | Target |
|-------------|--------|--------|
| No schema or config change | Migrations, config keys | None |
| No extra Jev calls | Questions per page | Unchanged |

---

## Constraints

- The owner's and admin replies (`/admin`, incidents) and the sign-in flow are out of scope.
- Standing waiver for human checkpoints (CLAUDE.local.md point 4).

---

## Assumptions

| Assumption | Risk if Invalid | Mitigation |
|------------|-----------------|------------|
| Times in UTC are acceptable | Users read the wrong local time | Times are labelled "UTC" as today |

---

## Open Questions

None. The owner decided on 2026-11-10 that an unchanged saving keeps alerting on every check.
