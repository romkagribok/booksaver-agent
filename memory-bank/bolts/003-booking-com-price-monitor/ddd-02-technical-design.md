---
unit: 002-booking-com-price-monitor
bolt: 003-booking-com-price-monitor
stage: design
status: complete
updated: 2026-07-05T00:00:00Z
---

# Technical Design — Booking.com Price Monitor

> Scope: Bolt `003-booking-com-price-monitor` — US-004/005/006/014.
> Translates `ddd-01-domain-model.md` into concrete Python. Introduces the first
> third-party runtime dependencies. Key library choices are flagged **[ADR]** for Stage 3.

## Architecture Pattern

Same **Hexagonal (Ports & Adapters)** layering as Unit 1. This bolt adds:

- A new `monitor/` package (application-layer services: `BookingComMonitor`, `SessionManager`, `FailureTracker`)
- Four new ports in `application/ports.py` (`BrowserSession`, `LLMExtractor`, `SessionRepository`, `CheckHistoryRepository` — finalised)
- Three new infrastructure adapters: Playwright (`browser/`), Anthropic SDK (`llm/`), JSON session file (`persistence/session_store.py`)
- New domain models: `CheckResult`, `SessionState`, and their value objects

The `monitor/` services are **pure application logic** — they call ports, never Playwright or `anthropic` directly. All browser/LLM/persistence coupling lives in `infrastructure/`.

## Package Layout Changes

```text
src/booksaver/
├── domain/
│   ├── check_result.py       # CheckResult aggregate + value objects
│   │                         #   (CheckOutcome, ExtractionMethod, RefundIndicators,
│   │                         #    ExtractedBookingFields, FailureReason)
│   └── session.py            # SessionState aggregate + SessionStatus enum
├── application/
│   └── ports.py              # + BrowserSession, LLMExtractor,
│                             #   SessionRepository, CheckHistoryRepository (finalised)
├── monitor/
│   ├── __init__.py
│   ├── check_job.py          # BookingComMonitor — registered as scheduler job
│   ├── session_manager.py    # SessionManager service
│   └── failure_tracker.py   # FailureTracker service
└── infrastructure/
    ├── browser/
    │   ├── __init__.py
    │   └── playwright_adapter.py   # BrowserSession → Playwright sync API  [ADR]
    ├── llm/
    │   ├── __init__.py
    │   └── anthropic_adapter.py    # LLMExtractor → Anthropic SDK          [ADR]
    └── persistence/
        ├── sqlite_store.py         # + SqliteCheckHistoryRepository (finalises stub)
        ├── session_store.py        # LocalSessionRepository — JSON cookie file
        └── schema.sql              # v2 migration: finalise check_history columns
```

No existing Unit 1 files are modified except:
- `application/ports.py` — four new Protocol interfaces appended
- `infrastructure/persistence/schema.sql` — v2 migration adding check_history columns
- `infrastructure/persistence/sqlite_store.py` — `SqliteCheckHistoryRepository` class added
- `cli/commands.py` — `booksaver auth` subcommand added (triggers browser login flow)
- `daemon/scheduler.py` / `check_job.py` — monitor job registered at startup in `cmd_run`

## Browser Automation **[ADR]**

**Playwright (Python), synchronous API (`sync_playwright`).**

`playwright.sync_api` provides a blocking interface identical in capability to the async version, which means the scheduler loop (already on the main thread) calls `run_check()` directly without threading complexity. Playwright manages a persistent browser context whose cookies are exported after login and imported before each check.

```python
# Conceptual (detail in playwright_adapter.py)
with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    context = browser.new_context()
    context.add_cookies(loaded_cookies)
    page = context.new_page()
    page.goto(booking_url)
    html = page.content()
    cookies = context.cookies()
```

Session flow:
1. **First run / reauth**: `booksaver auth` opens Chromium in **headed** mode (visible), user logs in manually, cookies saved to `{data_directory}/session_booking_com.json`.
2. **Subsequent checks**: cookies loaded from file → injected into a headless context → page opened → cookies refreshed and saved back after each run.

## LLM Extraction **[ADR]**

**Anthropic Python SDK (`anthropic`), `claude-haiku-4-5` model by default.**

DOM extraction is attempted first using CSS selectors. If the price element is not found or the value is ambiguous, the page's visible text is extracted and sent to the LLM with a structured extraction prompt.

```python
# Conceptual (detail in anthropic_adapter.py)
client = anthropic.Anthropic(api_key=config.llm_api_key)
response = client.messages.create(
    model=config.llm_model or "claude-haiku-4-5-20251001",
    max_tokens=256,
    messages=[{"role": "user", "content": EXTRACTION_PROMPT.format(page_text=text, booking=booking)}]
)
```

The extraction prompt asks for a JSON object: `{price, currency, is_refundable, cancellation_deadline, confidence}`. Low-confidence or parse-failed responses are treated as `extraction_failed` and logged.

## Module Design

### `domain/check_result.py`

```python
@dataclass(frozen=True)
class RefundIndicators: ...
@dataclass(frozen=True)
class ExtractedBookingFields: ...
@dataclass(frozen=True)
class FailureReason: ...

class CheckOutcome(Enum): SUCCESS = "success"; FAILURE = "failure"
class ExtractionMethod(Enum): DOM = "dom"; LLM = "llm"; NONE = "none"

@dataclass(frozen=True)
class CheckResult:
    check_id: str
    booking_id: str
    checked_at: datetime
    outcome: CheckOutcome
    live_price: Money | None          # required if outcome=SUCCESS
    refund_indicators: RefundIndicators | None
    extracted_fields: ExtractedBookingFields | None
    extraction_method: ExtractionMethod
    failure_reason: FailureReason | None  # required if outcome=FAILURE
```

### `domain/session.py`

```python
class SessionStatus(Enum): ACTIVE = "active"; EXPIRED = "expired"; REQUIRES_REAUTH = "requires_reauth"

@dataclass
class SessionState:
    session_id: str
    platform: Platform
    cookies: bytes           # opaque Playwright JSON blob
    authenticated_at: datetime
    expires_at: datetime | None
    status: SessionStatus
```

### `monitor/check_job.py` — `BookingComMonitor`

`run_check(booking)` sequence:
1. `session_manager.ensure_active()` → if `requires_reauth`, log and skip booking
2. `browser.restore_cookies(session.cookies)` → `browser.open_page(booking_url)`
3. Try DOM price extraction via CSS selector
4. If DOM fails → `llm_extractor.extract_price(page_text, booking)`
5. Build `CheckResult` (success or failure)
6. `check_history_repo.add(result)`
7. If success → `failure_tracker.reset(booking.booking_id)`
8. If failure → `failure_tracker.record_failure(...)` → emit `RepeatedFailureWarning` if threshold reached
9. Save refreshed cookies back to session

The check job is registered with the Scheduler in `cmd_run`:
```python
monitor = BookingComMonitor(browser, llm, session_mgr, check_repo, booking_repo, failure_tracker)
scheduler.register("booking_com_check", lambda: monitor.run_all_active())
```

### `monitor/session_manager.py` — `SessionManager`

- `ensure_active()`: loads session from `SessionRepository`, checks `expires_at`, transitions status if needed, returns `SessionState`
- No automatic reauth — reauth requires `booksaver auth` (user opens browser, logs in)

### `monitor/failure_tracker.py` — `FailureTracker`

- Reads last N check results from `CheckHistoryRepository.get_recent()`
- Counts consecutive failures from the tail
- Emits `RepeatedFailureWarning` (as a log line + optional future notification) when count ≥ threshold

## Data Persistence

### `check_history` table (v2 migration — finalises the Bolt 001 stub)

| Column | Type | Notes |
|--------|------|-------|
| `id` | INTEGER PK | auto-increment |
| `check_id` | TEXT UNIQUE NOT NULL | UUID |
| `booking_id` | TEXT NOT NULL FK→bookings | |
| `checked_at` | TEXT NOT NULL | ISO-8601 |
| `outcome` | TEXT NOT NULL | `success`/`failure` |
| `live_amount` | TEXT NULL | Decimal string, NULL on failure |
| `live_currency` | TEXT NULL | ISO-4217, NULL on failure |
| `extraction_method` | TEXT NOT NULL | `dom`/`llm`/`none` |
| `refundable` | INTEGER NULL | 1/0, NULL if not extracted |
| `cancellation_deadline` | TEXT NULL | ISO date string |
| `refund_raw_text` | TEXT NULL | verbatim page text for audit |
| `extracted_property` | TEXT NULL | |
| `extracted_room` | TEXT NULL | |
| `extracted_check_in` | TEXT NULL | |
| `extracted_check_out` | TEXT NULL | |
| `failure_code` | TEXT NULL | enum value, NULL on success |
| `failure_detail` | TEXT NULL | human-readable, NULL on success |

### Session file

`{data_directory}/session_booking_com.json` — Playwright cookies array (list of dicts), mode `0600`. Not stored in SQLite because browser contexts natively read/write cookie JSON.

## New CLI Surface

| Command | Purpose |
|---------|---------|
| `booksaver auth` | Opens Chromium in headed mode for manual Booking.com login; saves cookies locally on completion |

## Error Handling

| Error | Behaviour |
|-------|-----------|
| Session expired / reauth needed | Skip check, log `ReauthRequired`, emit warning; daemon continues |
| Navigation error (timeout, 404) | `CheckFailed` with `navigation_error`; booking untouched |
| Captcha / bot detection | `CheckFailed` with `auth_required`; suggest running `booksaver auth` |
| DOM extraction finds no price | Fall through to LLM extraction |
| LLM extraction fails / parse error | `CheckFailed` with `llm_error`; no crash |
| Repeated failures ≥ threshold | `RepeatedFailureWarning` logged; optionally surfaced via notification in Unit 3 |
| LLM API key missing | Logged at startup; LLM path skipped; DOM-only mode |

## New Runtime Dependencies

| Package | Purpose | Notes |
|---------|---------|-------|
| `playwright` | Browser automation | Requires `playwright install chromium` post-install |
| `anthropic` | LLM extraction | API key from env `BOOKSAVER_LLM_API_KEY` |

Both added to `pyproject.toml` `[project.dependencies]`. `playwright install chromium` documented in CLAUDE.md setup steps.

## Open Decisions for Stage 3 (ADR Analysis)

1. **Playwright** (vs Selenium/Puppeteer) as browser automation library.
2. **`sync_playwright`** (vs async) — avoids async complexity in the scheduler loop.
3. **Anthropic SDK + claude-haiku** (vs generic HTTP + any LLM) for extraction.
4. **JSON file** (vs SQLite) for session cookie storage — browser-native format.
