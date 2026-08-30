---
stage: test
bolt: 060-agentic-inventory-executor
created: 2026-08-30T18:43:23Z
---

# Test Report: Browser Use `/bookings` Inventory Executor

## Outcome

Passed. Browser Use is selected only for the agentic `/bookings` synchronization trigger and
remains behind BookSaver's existing session, validation, positive-only reconciliation, cost,
deadline, and persistence boundaries. Stagehand remains selected for post-connect, `/checknow`, and
scheduled inventory. Price execution is unchanged.

## Functional and Routing Evidence

- Coordinator tests prove `/bookings` constructs the Browser Use factory while `/checknow`
  constructs Stagehand and neither opens the legacy browser on the agentic route.
- Existing tests prove a terminal agentic result preserves last-safe state without same-job legacy
  fallback.
- Typed reservation and scope submissions map to the existing provider-neutral inventory result;
  malformed or unsupported terminals fail closed.
- Authentication is accepted only after the code-owned protected-account probes verify the live
  session; the provider cannot assert authentication or refreshed-cookie eligibility.

## Safety and Privacy Evidence

- The exact action registry contains only guarded click, scroll, key, wait, one-positive-reservation
  submission, and typed `done`; stock navigation, typing, tabs, files, extraction, scripts, and
  downloads are absent.
- Click tests cover nested unsafe anchors/forms, cross-target frames, overlong and multiply encoded
  mutation destinations, unsafe labels, and post-action destination checks.
- A real Chromium/CDP fixture triggers a cancellation-like JavaScript confirmation and proves the
  dialog is dismissed before its mutation callback runs.
- Downloads, persistent storage-state polling, popup auto-accept, external blank-page assets,
  permission grants, telemetry, cloud sync, version calls, and dependency log propagation are
  disabled. Screenshots remain in memory and all owned browser, profile, agent, config, and cache
  job-owned browser/profile/agent paths are removed on teardown, including the namespace created
  before a late Agent constructor failure. Process-wide content-free config/cache directories stay
  available for later Stagehand and Playwright work and are not used for page/session content.
- Browser page egress permits only HTTPS Booking application/static-delivery hosts and loopback;
  the live fixture blocks an external fetch. Anthropic traffic is emitted only by the metered local
  SDK, not by page tools.

## Cost, Limit, and Failure Evidence

- Every physical Browser Use inference is admitted and reconciled through the existing persisted
  budget. Tests cover ordinary usage, Anthropic cache reads/writes, provider failure, timeout,
  cancellation, admission denial, reconciliation failure, and execution-cost breach.
- Agent recovery is bounded to three failures, one action per step, the inherited residual action
  count, and the inherited absolute deadline. No SDK retry or fallback model is configured.
- Provider/page exception content and the Anthropic key are absent from model representations and
  BookSaver/dependency logs.

## Verification Commands

- `python3 -m pytest tests/unit/test_browser_use_inventory_executor.py -q` — 52 passed.
- Focused Browser Use/coordinator/guard slice — 130 passed.
- `python3 -m ruff check src tests` — passed.
- `python3 -m mypy src` — passed across 128 source files.
- `python3 -m pytest -q` — 1,859 passed, 55 pre-existing deprecation warnings.
- `git diff --check` — passed.

## Exact-Image Qualification

- `docker build --tag booksaver-agent:browser-use-candidate .` — passed; image
  `sha256:0a30c0020280ced3ef5013d674dbcecd2310f753897af7d752059acd642b292c`.
- The image installed `requirements.lock`, passed `pip check`, and asserted the qualified Browser
  Use, Browser Use SDK, Anthropic, Playwright, Pydantic, cdp-use, and bubus versions and imports.
- Non-root container smoke launched and closed the bundled Playwright Chromium successfully and
  printed `locked-browser-runtime-ok`; the CLI help smoke passed.

## Residual Live Qualification

The browser network guard intentionally blocks third-party analytics, identity, consent, and AWS
WAF SDK hosts. Booking's own `booking.com` and `bstatic.com` application delivery is allowed. The
merged x86_64 VPS image and authenticated Telegram `/bookings` run remain the release acceptance
test; any ordinary eligible flow that requires a currently blocked third-party host must be
diagnosed from content-free counters before the egress policy changes.
