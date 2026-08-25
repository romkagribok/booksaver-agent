# Release d5079b0 — agentic browser owner canary

## Release identity

- Released at: `2026-08-25T01:30:49Z`
- Environment: owner-operated production VPS (hostname redacted)
- Source and runtime source: `main` at `d5079b0243beefc81bb728f3b80caf6da6fd2879`
- Previous deployed runtime source: `65633bed3be858041c17e215eb07e750dbdc955f`
- GitHub delivery: PR #27 for the bounded agentic executor and PR #28 for Docker launch
  compatibility; both passed a successful current-head Cursor Bugbot merge gate.
- Release scope: enable `owner_canary` routing for the local Stagehand 4.0.1 semantic executor and
  guarded Anthropic computer-use fallback while invited users remain on the legacy price path.

## AI-DLC construction evidence

- Correction bolt `054-local-agentic-price-executor` added US-155 after the first exact-image smoke
  proved Stagehand's generic `CI` inference omitted the Chromium flag already required by the
  established Playwright Docker runtime.
- The adapter now passes `chromium_sandbox=False` explicitly while BookSaver and Chromium remain the
  unprivileged `booksaver` user. No privileged container, host browser service, new capability,
  remote browser, or change to action/destination/session/routing guards was introduced.
- Local release gate: 34 focused tests and 1,695 repository tests passed; Ruff passed; strict mypy
  passed across 124 source files; CLI/config/package smoke passed; AI-DLC artifact validation and
  status integrity reported zero issues.
- Bolt 054 and US-155 completed through the mandatory AI-DLC completion cascade. Bolt 052 remains
  in progress at the authentic live-owner-canary checkpoint.

## Build and staging evidence

- Exact staged and production image ID:
  `sha256:a47199c4f82374da4f7349095b420a0c42f67d0c5e27160ff43d1e71b9b244a5`.
- Image size: 635,394,911 bytes.
- Stagehand 4.0.1 and Anthropic SDK 1.0.0 were present in the image; raw Playwright launched the
  installed Chromium `151.0.7922.34`.
- With `CI` absent and external networking disabled, Stagehand launched Chromium, exposed loopback
  CDP, attached with loopback-only telemetry, and tore down without a remaining container.
- The owner-canary configuration passed BookSaver validation and Compose resolution.
- A runtime-UID-writable clone of the fresh schema-15 production backup migrated to schema 16 with
  SQLite integrity `ok`, zero foreign-key violations, all common-table row counts unchanged, and all
  three new agentic tables empty.
- Staging did not use an Anthropic API key, authenticated Booking.com session, live price check, or
  synthetic canary record.

## Deployment record

The prior production image was tagged `booksaver-agent:rollback-65633be-pre-d5079b0`. A fresh online
SQLite backup, `config.toml`, and `.env` were preserved before promotion. The database backup passed
integrity and foreign-key checks at schema 15.

The VPS checkout was fast-forwarded to the merge SHA while preserving untracked operator artifacts.
The validated owner-canary configuration was installed atomically, the exact staged image was
promoted to `booksaver-agent:latest`, and only the BookSaver service was recreated with no
dependencies. Caddy retained the same container identity and `2026-07-26T23:20:44Z` start time.

After verification, the cloned database volume, temporary staging worktrees/scripts, candidate
configs, and staging image tags were deleted. Production and rollback artifacts were retained.

## Production verification

- Active checkout and BookSaver image resolve exactly to merge `d5079b0` and the staged image ID.
- BookSaver is healthy with zero restarts and no OOM kill; it runs as UID 1000 and held approximately
  34 MiB of its 2 GiB memory limit during verification.
- Caddy remained continuously running and was not recreated.
- Live SQLite migrated from schema 15 to 16 with integrity `ok`, zero foreign-key violations, and all
  common-table row counts preserved. Normal startup retention pruned one expired DOM diagnostic;
  no business or audit aggregate changed. Agentic canary, consent, and promotion tables remain empty.
- Effective routing is `owner_canary`; qualification is `unqualified` with zero owner checks and all
  live count/span/manual-comparison/reliability gates still closed.
- Release-window logs and two post-deploy monitors reported zero errors, warnings, restarts, or OOM
  events; heartbeat age stayed below 10 seconds.
- The idle container had no Chromium process and BookSaver published no host ports directly.
- Telegram Bot API and all 11 configured commands succeeded; public `/healthz` returned 200;
  Booking.com returned 202; the Anthropic endpoint was reachable with its expected unauthenticated
  404 response.

## User acceptance and live qualification

The owner should run `/status`, `/bookings`, and `/checknow` from Telegram. Automated deployment
verification did not impersonate a Telegram user, start a second coordinator, consume model budget,
or create live canary evidence.

An eligible owner `/checknow` may now use the agentic executor. Invited users remain legacy-routed.
Invited-user promotion still requires at least 30 authentic owner checks across 14 days, 10 manual
comparisons, every quantitative cost/reliability/duration/fallback gate, zero critical violations,
current disclosure consent, and explicit owner promotion.

## Rollback readiness

- Previous image tag: `booksaver-agent:rollback-65633be-pre-d5079b0`.
- Pre-deployment schema-15 database backup: `/data/booksaver.db.pre-d5079b0` inside the BookSaver
  data volume.
- Operator backups: `config.toml.pre-d5079b0` and `.env.pre-d5079b0` in
  `/opt/booksaver-agent`.

Routing can be returned to `legacy` with the current image without restoring data. Exact rollback to
the pre-agentic `65633be` image also requires the saved schema-15 database because that binary
predates schema 16. Restoring the database would discard post-deployment state and therefore
requires separate explicit data-loss approval.
