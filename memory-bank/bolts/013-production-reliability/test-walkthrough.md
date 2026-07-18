---
stage: test
bolt: 013-production-reliability
created: 2026-07-18T18:10:28Z
---

## Test Report: production-reliability

### Summary

- **Focused tests**: 60/60 passed.
- **Full suite**: 650/650 passed.
- **Coverage**: Not measured; this repository has no configured coverage threshold for this bolt.
- **Ruff**: Passed for `src/` and `tests/`.
- **Mypy**: Passed with no issues across 72 source files.
- **Whitespace validation**: `git diff --check` passed.
- **Wheel build**: Passed; `booksaver_agent-0.1.0-py3-none-any.whl` built successfully.
- **Installed-wheel smoke test**: Passed; a fresh SQLite database initialized at schema version 8
  with the required `bookings`, `check_history`, and `users` tables.

### Test Files

- [x] `tests/unit/monitor/test_browser_agent.py` - Verifies two-execution containment, five-proposal
  give-up, fresh screenshots, durable blocked traces, terminal destructive guard behavior, existing
  blocked-URL behavior, and budget caps.
- [x] `tests/unit/monitor/test_journey_escalation.py` - Verifies successful LLM recovery, safe
  `fill_search` give-up continuation, terminal failure at other steps, bot-wall handling, and budgets.
- [x] `tests/unit/monitor/test_search_journey.py` - Verifies production-shaped calendar drift,
  screenshot-first escalation, both allowed fallback codes, exact trusted dates/occupancy, terminal
  guard rejection, and downstream context verification after fallback.
- [x] `tests/unit/telegram/test_commands_readonly.py` - Verifies full help/start discovery, exact IDs,
  unique displayed prefixes, short/ambiguous references, and cross-user non-disclosure.
- [x] `tests/unit/test_packaging.py` - Verifies the persistence schema package-data declaration.
- [x] Full existing test suite - Verifies no regression across configuration, persistence, scheduler,
  monitoring, savings, notifications, rebook gates, Telegram access, and deployment behavior.

### Acceptance Criteria Validation

- ✅ **Visual observation**: Recovery receives a screenshot on visual-step entry and again after a
  duplicate proposal is refused.
- ✅ **Duplicate containment**: Only the first two identical non-progressing actions reach the browser;
  later copies are refused and traced, and the fifth identical proposal returns `AGENT_GAVE_UP`.
- ✅ **Guard and budgets**: A destructive target returns terminal `BLOCKED_ACTION`; blocked landing
  URLs and existing budget codes remain terminal and distinct.
- ✅ **LLM-first recovery**: The scripted `fill_search` failure invokes screenshot-aware escalation
  before any trusted-data continuation.
- ✅ **Fallback boundary**: Only `FILL_SEARCH` with `AGENT_GAVE_UP` or `BUDGET_EXCEEDED` continues;
  guard rejection and failures at other steps remain failed checks.
- ✅ **Trusted search data**: The results URL contains persisted check-in, check-out, adults, children,
  and room count values.
- ✅ **Downstream verification**: Incorrect context on the property page still fails at
  `VERIFY_CONTEXT` after fallback.
- ✅ **Wheel resource**: The built archive contains
  `booksaver/infrastructure/persistence/schema.sql` (5,513 bytes).
- ✅ **Fresh installed runtime**: Installing that wheel into an isolated target and opening an empty
  database initializes schema version 8/8 without `FileNotFoundError`.
- ✅ **Telegram discovery**: `/start` and `/help` contain the complete command reference, including
  registration, key management, and owner administration.
- ✅ **Telegram identifiers**: Exact caller-owned IDs and unique prefixes of at least eight characters
  resolve; short, ambiguous, missing, and cross-user references use the same not-found response.
- ✅ **No architecture expansion**: No dependency, schema migration, runtime process, or ADR was added.

### Verification Commands and Evidence

- Focused pytest selection: 60 passed in 0.22 seconds.
- Full `python3 -m pytest -q`: 650 passed in 5.45 seconds.
- `python3 -m ruff check src/ tests/`: all checks passed.
- `python3 -m mypy src/`: no issues in 72 source files.
- `git diff --check`: clean.
- Wheel archive inspection: schema resource present, 5,513 bytes.
- Installed-wheel fresh initialization: schema version 8/8; required tables present.

### Issues Found

- **Application safety issue found during Stage 2 reconciliation**: destructive guard rejection could
  continue the agent loop and later become fallback-eligible `AGENT_GAVE_UP`. Corrected to terminal
  `BLOCKED_ACTION` and covered by regression tests.
- **Test harness issue**: The first installed-wheel smoke command had a quoting syntax error before
  importing BookSaver. The corrected harness ran successfully; this was not an application failure.
- **Remaining product issues**: None found by automated, static, packaging, or isolated-install tests.

### Known Validation Debt Outside This Bolt

The AI-DLC global artifact validator still reports the previously disclosed legacy inconsistencies in
intents 001–003 (story frontmatter IDs versus filenames and four bolt-009 references). No new
intent-004 naming, timestamp, cross-reference, or status inconsistency was introduced. Those
historical migrations are outside bolt 013 and do not affect runtime verification.

### Notes

Docker execution and a live Booking.com/Telegram smoke test were not run locally. After final bolt
approval, commit, and push, the operator should rebuild the VPS image and trigger a real check through
Telegram; that is Operations work and the user's stated next validation step.
