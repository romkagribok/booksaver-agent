# Release b0b6757 — Browser Use default price execution

## Release identity

- Released at: `2026-09-03T01:54:00Z`
- Environment: owner-operated production VPS (hostname redacted)
- Source and runtime source: `main` at `b0b6757017fd92a7604dafa0462f15af48f6ed72`
- Previous deployed source: `721119f69cf1bef8acceacadf913ed1f778a02b4`
- GitHub delivery: PR #42. Cursor Bugbot was attempted on the final proposed head but reported that
  its usage limit was reached. The owner explicitly authorized proceeding when Bugbot was
  unavailable; this release records an exception, not a clean Bugbot pass.
- Release scope: make local Browser Use the default `PriceBrowserExecutor` for manual and scheduled
  checks, use Browser Use for every agentic inventory prerequisite, and retain Stagehand and the
  deterministic path as explicit future-job rollback choices.

## AI-DLC construction evidence

- Intent 023 Unit 006, Bolt 064, FR-13 through FR-20, and US-164 through US-169 completed through
  domain model, technical design, ADR analysis, implementation, and test.
- Browser Use receives only guarded read-only actions and typed observation authority. BookSaver
  retains authentication, property/query validation, all-in currency-aligned pricing,
  refundability, room equivalence, savings, persistence, and notification authority.
- The adapter contains no Booking.com CSS selector, test ID, or exact nesting dependency. A
  verified canonical property URL is used directly when available, with semantic search for
  name-only records.
- Query facts and offers are submitted atomically. BookSaver may ignore only recognized
  flexible/refundable rate-plan suffixes after a separator; bed, accessibility, and other room
  variants remain identity-bearing.
- Browser Use failure is terminal for the job. No Stagehand or deterministic same-job fallback is
  allowed.
- Local release gate: Ruff passed; strict mypy passed over 129 source files; all 1,925 tests passed
  with 55 existing deprecation warnings; CLI startup, artifact validation, status integrity, and
  whitespace validation passed.

## Build and staged replay evidence

- Exact production image ID:
  `sha256:1b8a1c39b69d428f0f9103e1261e343b586032060c9ae6e27bd923b05e10f49a`.
- OCI revision label exactly matches merge SHA `b0b6757`.
- Browser Use 0.11.13, Anthropic SDK 0.125.0, Playwright 1.62.0, and the image-qualified Chromium
  runtime are installed.
- Before promotion, exact candidate image `candidate-f5cea35` ran without source mounts against an
  isolated read-only clone of production state. It returned a BookSaver-accepted authenticated USD
  observation in 81,436 ms at USD 0.175276, with zero guard violations and no fallback.

## Deployment record

- Previous image rollback tag:
  `booksaver-agent:rollback-721119f-20260903T014708Z`.
- Quiesced data-volume, config, and environment backup:
  `/opt/booksaver-backups/20260903T014708Z-pre-browser-use-price/`.
- The backup checksum, SQLite integrity check, and foreign-key check passed against an isolated
  writable extraction; production state was not restored or mutated.
- The VPS checkout fast-forwarded to the merge SHA while preserving existing untracked operator
  files. Only the BookSaver service was recreated; Caddy retained its container identity.

## Production verification

- Active checkout, running image, and OCI revision label resolve to `b0b6757`.
- Effective config is `owner_canary` price routing, `browser_use` price execution, `agentic`
  inventory routing, Anthropic disclosure v1, USD 1/check, and USD 10/deployment-day.
- The exact deployed `latest` image repeated the isolated full coordinator replay. Browser Use
  performed current-run inventory verification and price execution; BookSaver accepted the current
  authenticated USD observation in 81,870 ms at USD 0.175606, with zero violations and no fallback.
- BookSaver is healthy with zero restarts and no OOM kill. Internal `/healthz` returned 200; release
  logs contained no traceback, critical, unhandled, exception, or error matches.
- SQLite is at schema 18 with integrity `ok`, zero foreign-key violations, three users, and two
  monitoring bookings.
- Idle memory was 35.5 MiB of the 2 GiB limit and no Chromium/Chrome process remained after replay.
- Caddy retained its pre-release container identity and public 80/443 bindings.

## Qualification and user acceptance

The deployed flow is accepted for the owner canary. It is not yet qualified for invited-user
promotion: collect at least 30 eligible checks over at least 14 days, manually compare at least 10
observations, and enforce the reliability, correctness, safety, p95, and USD 0.10 average-cost gates.
The two live release replays were below the USD 0.25 owner-canary average threshold and the USD 1
hard cap.

The owner may run `/checknow` in Telegram as a human-facing acceptance check. The operator replay
already exercised and waited for the same deployed coordinator, Browser Use inventory prerequisite,
Browser Use price executor, and BookSaver validation boundary without sending notifications.

## Rollback readiness

- Runtime rollback: retag `booksaver-agent:rollback-721119f-20260903T014708Z` as
  `booksaver-agent:latest` and recreate only BookSaver.
- Adapter rollback for a future job: explicitly select Stagehand or the deterministic route; never
  resume a failed Browser Use job with another harness.
- Restoring the data archive would discard post-backup state and requires separate explicit
  data-loss approval.
