---
unit: 001-search-journey-monitor
bolt: 006-search-journey-monitor
stage: model
status: complete
updated: 2026-07-05T23:30:00Z
---

# Domain Model — Search Journey Monitor

> Scope: Bolt `006-search-journey-monitor` — **US-017** (occupancy), **US-018** (scripted
> search journey), **US-019** (equivalent-offer extraction + savings integration).
> Replaces the manage-page price source from bolt 003; downstream Savings/Notifications/
> Rebook contexts are frozen regression surfaces. No source code in this stage.

## Bounded Context

**Search Journey Monitor** extends the Booking.com Price Monitor context. It owns:

1. **Occupancy** — the party size a booking was made for; part of the `Booking` aggregate,
   required for any search-based price check.
2. **The search journey** — a fixed sequence of named steps that re-search the registered
   property and dates on Booking.com as a returning customer (saved session), ending on a
   verified property page.
3. **Equivalent-offer extraction** — turning the property page's room/rate table into
   candidate offers, excluding non-equivalent or non-refundable ones, and selecting the
   cheapest survivor as the check's live price.

It **produces** the same `CheckResult` aggregate as bolt 003 — Unit 3's savings gate and
everything after it are unchanged consumers.

## Domain Entities

| Entity | Properties | Business Rules |
|--------|------------|----------------|
| **Booking** (extended) | + `occupancy` (Occupancy, nullable in storage) | New registrations MUST carry occupancy. A `None` occupancy is the *legacy-migrated* state only: checks against such a booking fail with `OCCUPANCY_MISSING` (never a silent default); a CLI backfill sets it exactly once |
| **SearchJourney** (per-check execution) | ordered `JourneyStep`s, per-step `StepOutcome`, terminal `JourneyResult` | Steps execute in fixed order; the first failed step aborts the journey; every step outcome is reportable (bolt 007 attaches agent escalation at exactly these seams) |

## Value Objects

| Value Object | Properties | Constraints |
|--------------|------------|-------------|
| **Occupancy** | `adults` (int), `children` (int), `rooms` (int) | `adults >= 1`, `children >= 0`, `rooms >= 1`; immutable |
| **JourneyStep** | enum: `open_home`, `dismiss_overlays`, `fill_search`, `submit_search`, `locate_property`, `open_property`, `verify_context`, `read_room_table` | Fixed order; names are stable identifiers used in step outcomes, logs, failure details, and (bolt 007) traces + escalation points |
| **StepOutcome** | `step` (JourneyStep), `ok` (bool), `detail` (str) | Immutable; failed outcome carries a human-readable reason |
| **OfferCandidate** | `room_label` (str), `total` (Money), `is_refundable` (bool \| None), `cancellation_text` (str \| None), `matches_room` (bool), `match_confidence` (0.0–1.0) | The all-in bookable total as displayed (incl. shown taxes/charges); `matches_room` judged against the booking's `RoomType` |
| **OfferSelection** | `chosen` (OfferCandidate \| None), `rejected_counts` (per exclusion reason) | `chosen` is the cheapest candidate with `is_refundable is True`, `matches_room is True`, and `match_confidence >= threshold` (0.5, same as bolt 003) |

## Selection / Exclusion Rules (US-019)

A candidate is **excluded** when any of:

1. `is_refundable` is `False` **or** `None` — refundability must be positively evidenced
   (cancellation-policy text), mirroring the US-008 rule that absence rejects.
2. `matches_room` is `False`, or `match_confidence < 0.5` — naming drift may be bridged by
   LLM judgment, but low confidence is exclusion, never a guessed savings signal.
3. Its total's currency differs from the baseline currency — the existing
   `CURRENCY_MISMATCH` rule would reject it anyway; excluding it here picks a comparable
   candidate instead of failing the whole check.

Zero surviving candidates → check failure `NO_EQUIVALENT_OFFER` (a legitimate, common
outcome — e.g. the room type is sold out — and never a savings signal).

## Mapping to CheckResult (the downstream contract)

The savings gate (`evaluate_equivalence`, US-008) rejects on any *contradicting* extracted
field and demands positively-confirmed refundability. The journey verifies property
identity and dates **upstream** and judges room equivalence with drift tolerance, so the
emitted `CheckResult` must not re-litigate that with naive string equality:

- `live_price` = chosen candidate's all-in total.
- `refund_indicators` = `is_refundable=True` + the candidate's raw cancellation text.
- `extracted_fields.property_name` / `check_in` / `check_out` = the values **as verified**
  during `locate_property` / `verify_context` (they equal the booking's own values, or the
  journey would have failed with `PROPERTY_NOT_FOUND` / a `verify_context` step failure).
- `extracted_fields.room_label` = the candidate's displayed label **only when it equals
  the booking's label** (case-insensitive); on drift-matched candidates it is `None`
  (absence = non-contradiction) and the actual label is logged (bolt 007: traced).
- `extraction_method` = `dom` when the room table was parsed by DOM heuristics, `llm` when
  LLM offer extraction produced the candidates.

## New Failure Codes

| Code | Meaning | Emitted by |
|------|---------|------------|
| `OCCUPANCY_MISSING` | Legacy booking has no occupancy; user must run the backfill CLI | pre-journey guard |
| `STEP_FAILED` | A scripted journey step failed (detail names the step) | any step (bolt 007 turns this into an escalation trigger first) |
| `PROPERTY_NOT_FOUND` | Registered property could not be located/verified in search results | `locate_property` |
| `NO_EQUIVALENT_OFFER` | Room table parsed, but no equivalent refundable candidate survived exclusion | `read_room_table` selection |
| `BOT_WALL` | Captcha / bot-detection interstitial encountered | any step |

Existing codes (`AUTH_REQUIRED`, `NAVIGATION_ERROR`, `EXTRACTION_FAILED`, `LLM_ERROR`,
`TIMEOUT`, `UNKNOWN`) keep their meanings.

## Domain Events

| Event | Trigger | Payload |
|-------|---------|---------|
| **JourneyCompleted** | All steps succeeded and a candidate was selected | `bookingId`, chosen candidate, step outcomes |
| **JourneyAborted** | A step failed or selection was empty | `bookingId`, failing step, failure code |
| **OccupancyBackfilled** | CLI sets occupancy on a legacy booking | `bookingId`, occupancy |

(Events remain implicit — log lines + CheckResult records — consistent with bolts 001–005.)

## Domain Services

| Service | Operations | Dependencies |
|---------|------------|--------------|
| **SearchJourney** | `run(booking) -> JourneyResult` — executes the step sequence against an interactive browser; aborts on first failure | `InteractiveBrowser` port |
| **OfferSelector** | `select(candidates, booking) -> OfferSelection` — applies the exclusion rules; pure function, fully unit-testable | none |
| **BookingComSearchMonitor** | `run_check(booking) -> CheckResult`, `run_all_active() -> list[CheckResult]` — occupancy guard → session restore → journey → extraction → selection → CheckResult; never raises | SearchJourney, `LLMExtractor` (offer extraction), SessionManager, CheckHistoryRepository, FailureTracker |

## Port Changes (application layer)

| Port | Change |
|------|--------|
| **InteractiveBrowser** (new) | Interactive superset of `BrowserSession`: `goto`, `click`, `fill`, `press`, `wait_for`, `snapshot` (url/title/visible text), plus the existing cookie/auth operations. Designed so bolt 007's agent can drive the same port |
| **LLMExtractor** (extended) | + `extract_offers(page_text, booking) -> list[OfferCandidate]` — one call interprets the room table and judges room-match per candidate |
| **BookingRepository** (extended) | + `set_occupancy(booking_id, occupancy)` for the CLI backfill |

## Persistence Impact

Schema **v5** (single migration for the whole intent):

1. `bookings` + nullable `occ_adults`, `occ_children`, `occ_rooms` columns (legacy rows
   stay NULL = occupancy-missing state; domain enforces the invariant for new rows).
2. `check_history` rebuilt once to relax `extraction_method` CHECK to
   `('dom','llm','none','agent')` — `agent` is reserved for bolt 007, avoiding a second
   table rebuild in the same intent.
