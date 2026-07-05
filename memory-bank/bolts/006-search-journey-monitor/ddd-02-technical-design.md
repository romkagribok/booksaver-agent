---
unit: 001-search-journey-monitor
bolt: 006-search-journey-monitor
stage: design
status: complete
updated: 2026-07-05T23:35:00Z
---

# Technical Design — Search Journey Monitor

> Scope: US-017, US-018, US-019. Hexagonal layout preserved (ADR-004); runtime deps stay
> playwright + anthropic (ADR-003/007/009).

## Module Map

| Module | Role | New/Changed |
|--------|------|-------------|
| `domain/value_objects.py` | + `Occupancy` frozen dataclass (validating `__post_init__`) | changed |
| `domain/models.py` | `Booking` + `occupancy: Occupancy \| None = None`; `Booking.create(..., occupancy)` requires it | changed |
| `domain/check_result.py` | + `FailureCode` members: `OCCUPANCY_MISSING`, `STEP_FAILED`, `PROPERTY_NOT_FOUND`, `NO_EQUIVALENT_OFFER`, `BOT_WALL` | changed |
| `domain/offer.py` | `OfferCandidate`, `OfferSelection`, `select_offer()` (pure exclusion/selection rules) | **new** |
| `domain/journey.py` | `JourneyStep` enum, `StepOutcome`, `JourneyResult` | **new** |
| `application/ports.py` | + `InteractiveBrowser` Protocol, `PageSnapshot`; `LLMExtractor` + `extract_offers`; `BookingRepository` + `set_occupancy` | changed |
| `monitor/search_journey.py` | Scripted step implementations + orchestration (`SearchJourney.run`) | **new** |
| `monitor/room_table.py` | DOM-heuristic candidate parsing from property-page text/HTML | **new** |
| `monitor/search_check_job.py` | `BookingComSearchMonitor` — occupancy guard, session handling, journey, extraction, selection, CheckResult; replaces `BookingComMonitor` in the daemon wiring | **new** |
| `monitor/check_job.py` | Retired from the daemon path (kept only as session-validation reference until bolt 007 removes remaining uses; `myreservations.html` no longer visited for prices) | changed |
| `infrastructure/browser/playwright_adapter.py` | + `PlaywrightInteractiveBrowser` implementing `InteractiveBrowser` (persistent page, selector actions, snapshot) | changed |
| `infrastructure/llm/anthropic_adapter.py` | + `extract_offers` prompt/parser (JSON array of candidates with match judgment) | changed |
| `infrastructure/persistence/schema.sql` + `sqlite_store.py` | v5 migration (occupancy columns; check_history CHECK rebuild); repo mapping + `set_occupancy` | changed |
| `cli/commands.py` | `register` gains `--adults/--children/--rooms`; new `bookings set-occupancy`; `bookings list` shows occupancy | changed |

## The Journey (US-018)

`SearchJourney.run(booking)` executes fixed steps against `InteractiveBrowser`; the first
failure aborts and maps to a coded `CheckResult` failure. Steps and their scripted
implementations:

| Step | Scripted implementation | Failure mapping |
|------|------------------------|-----------------|
| `open_home` | `goto("https://www.booking.com")` | `NAVIGATION_ERROR` |
| `dismiss_overlays` | best-effort click on known consent/genius popups (`#onetrust-accept-btn-handler`, `[aria-label*="Dismiss"]`); absence is success | never fails hard; `BOT_WALL` if captcha markers detected |
| `fill_search` | `fill('[name="ss"]', property.name)`; open date panel (`[data-testid="searchbox-dates-container"]`); click `[data-date="<check_in>"]`, `[data-date="<check_out>"]`; occupancy panel (`[data-testid="occupancy-config"]`) → set `group_adults`, `group_children`, `no_rooms` | `STEP_FAILED` |
| `submit_search` | `click('button[type="submit"]')`, wait for `[data-testid="property-card"]` | `STEP_FAILED` |
| `locate_property` | scan property cards' `[data-testid="title"]`; normalized name match against `property.name` (and `booking_com_ref` slug when the ref is a URL) | `PROPERTY_NOT_FOUND` |
| `open_property` | click the matched card's title link; wait for room table anchor (`#hprt-table`, `[data-testid*="rt-"]` fallbacks) | `STEP_FAILED` |
| `verify_context` | assert check-in/check-out and occupancy visible on the property page match the booking (URL params `checkin=`/`checkout=`/`group_adults=` or availability-bar text) | `STEP_FAILED` |
| `read_room_table` | snapshot page; candidates via `room_table.parse()` DOM heuristics; LLM `extract_offers` fallback (below) | `EXTRACTION_FAILED` / `NO_EQUIVALENT_OFFER` |

Booking.com selectors WILL drift — that is accepted here: a drifted selector is a
`STEP_FAILED` with the step name in the detail, which is precisely the escalation seam
bolt 007 plugs the LLM agent into. Auth loss detected via existing sign-in markers →
`AUTH_REQUIRED`; captcha markers (`hcaptcha`, "are you a human", `px-captcha`) → `BOT_WALL`.

## Extraction & Selection (US-019)

1. **DOM heuristics** (`monitor/room_table.py`): parse room-table rows from page text/HTML
   (label, price, "Free cancellation"/"Non-refundable" phrases). A candidate whose
   normalized label equals the booking's room label AND has explicit refundability text is
   a *confident exact match* — no LLM call needed.
2. **LLM offer extraction** (when DOM finds no confident exact match): one
   `extract_offers` call with the property-page visible text (bounded to 30k chars, as
   bolt 003) returning a JSON array: `[{room_label, price, currency, is_refundable,
   cancellation_text, matches_room, match_confidence}]`. Malformed reply → empty list
   (zero-confidence pattern from bolt 003's parser).
3. **Selection** (`domain/offer.select_offer`): pure function applying the exclusion rules
   (refundable-confirmed only, room-matched ≥ 0.5, baseline currency) → cheapest survivor.
4. **CheckResult mapping** exactly per the domain model (verified fields; drift-matched
   room label emitted as `None`; method `dom` or `llm`).

Happy-path LLM budget: 0 calls (confident exact DOM match) or 1 call (`extract_offers`) —
within the ≤ 2 NFR.

## Occupancy (US-017)

- `Occupancy(adults, children, rooms)` validated in `__post_init__`.
- `Booking.create()` takes `occupancy` as a required parameter; the dataclass field is
  `Occupancy | None` solely so migrated legacy rows can hydrate.
- Migration v5: `ALTER TABLE bookings ADD COLUMN occ_adults/occ_children/occ_rooms`
  (nullable); `check_history` rebuilt (create-copy-drop-rename) with `extraction_method`
  CHECK extended to include `'agent'`.
- Monitor guard: `booking.occupancy is None` → `CheckResult.failure(OCCUPANCY_MISSING,
  "Run: booksaver bookings set-occupancy <id> --adults N")` without opening a browser.
- CLI: `register --adults N [--children 0] [--rooms 1]` (adults required; children/rooms
  are explicit, documented defaults); `bookings set-occupancy <booking-id> --adults N
  [--children N] [--rooms N]`; `bookings list` gains an `OCC` column (`2+0/1` format,
  `MISSING` marker for legacy rows).

## Daemon Wiring (US-019 / FR-5)

`cli/commands.py::_make_check_job` constructs `BookingComSearchMonitor` with
`PlaywrightInteractiveBrowser` instead of `BookingComMonitor` + `open_page`. Session
restore/refresh, failure tracking, and the savings pipeline call stay byte-identical.
`is_authenticated` remains snapshot-marker based; the manage page is never opened.

## Testing Strategy (stage 5 preview)

- `Occupancy` validation + `Booking.create` requirement + migration behavior (legacy NULL
  rows hydrate to `None`, checks fail `OCCUPANCY_MISSING`, backfill un-blocks) — SQLite tmp DBs.
- `SearchJourney` against a `FakeInteractiveBrowser` scripted with canned snapshots per
  step: happy path, per-step failures, captcha page, auth-loss page.
- `room_table.parse` on captured/synthetic room-table text fixtures.
- `select_offer` exclusion-rule matrix (refundability absent/false, low confidence,
  currency mismatch, cheapest-of-several, empty).
- `extract_offers` parser: valid array, malformed JSON, out-of-range confidence.
- Regression: entire existing suite (211 tests) must stay green; savings pipeline consumes
  the new monitor's results in an end-to-end fake-browser test.
