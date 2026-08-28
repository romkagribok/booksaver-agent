# Release 88eeac7 — agentic inventory provider schemas

## Release identity

- Released at: `2026-08-28T02:14:32Z`
- Environment: owner-operated production VPS (hostname redacted)
- Source and runtime source: `main` at `88eeac7914fd9c0fe1d8923383f2ff428ec114d4`
- Previous deployed runtime source: `37e54b26096c57f77d164c915864d96b7301bb65`
- GitHub delivery: PR #33; Cursor Bugbot found two fail-closed decoding issues on the first head,
  both were fixed with regressions, and the successful current-head merge gate passed at
  `49ee00e0cc4fd41f9518fb8f4bd1abe7c3f0b544` before merge.
- Release scope: make Stagehand scope/detail extraction and guarded Anthropic computer use use
  provider-compatible schemas while BookSaver retains all evidence, action, reconciliation,
  session, deadline, and cost authority.

## AI-DLC construction evidence

- Corrective bolt `058-agentic-inventory-executor` and US-158 completed through the DDD stages and
  mandatory completion cascade under ADR-036, ADR-037, ADR-039, and ADR-040.
- Stagehand extraction uses zero provider-compiled union parameters and explicit string sentinels;
  unknown completeness remains fail-closed `incomplete` evidence.
- Unsupported Anthropic strict-schema constraints are removed. The large observation tool remains
  untrusted and non-strict because it exceeds the provider grammar-size ceiling; typed decoding and
  code-owned collection/count bounds are enforced before BookSaver validation.
- Bugbot regressions prove non-strict JSON booleans decode without acquiring positive authority and
  malformed occupancy remains unknown rather than discarding identity-valid evidence.
- Local release gate: 1,795 tests passed with 55 existing deprecation warnings; Ruff and strict mypy
  passed across 127 source files; artifact validation and status integrity reported zero issues
  across 58 bolts and 23 intents; `git diff --check` passed.

## Build and staging evidence

- Exact staged and production image ID:
  `sha256:ca7feba38f71cdee42069e64cb56940d5ed2287cd95b19ad8a10e6fa2b4eaf17`.
- Image size: 635,764,298 bytes; OCI revision label exactly matches merge SHA `88eeac7`.
- Stagehand 4.0.1, Anthropic SDK 1.2.0, and Chromium 151.0.7922.34 were present and launchable in
  the exact image.
- A runtime-writable clone of the fresh production backup opened at schema 17 with SQLite integrity
  `ok`, zero foreign-key violations, and unchanged counts: three users, four account reservations,
  two monitoring bookings, 20 check-history rows, 218 synchronization runs, and seven redacted
  agentic inventory execution records.
- Production config validation passed with independent `owner_canary` price routing and `agentic`
  inventory routing.
- Cookie-free exact-image provider smokes reached Anthropic through Stagehand and returned typed
  `unavailable` terminals for both scope and detail extraction. A direct guarded computer-use call
  also proved Anthropic accepted the final tool schemas. No authenticated page content, cookies, or
  screenshots were retained.

## Deployment record

The previous production image was tagged
`booksaver-agent:rollback-37e54b2-pre-88eeac7`. A fresh online schema-17 SQLite backup,
`config.toml`, and `.env` were preserved before promotion. The backup passed integrity and
foreign-key checks.

The VPS checkout was fast-forwarded to the merge SHA while preserving untracked operator files.
The exact staged image was promoted to `booksaver-agent:latest`, and only the BookSaver service was
recreated with no dependencies. Caddy retained its container identity and
`2026-07-26T23:20:44Z` start time.

After production verification, the cloned staging volume, staging image tags, and temporary build
directory were deleted. Production and rollback artifacts were retained.

## Production verification

- Active checkout, OCI label, `latest` tag, and running BookSaver image all resolve exactly to merge
  `88eeac7` and image `ca7feba`.
- BookSaver became healthy after three polls, remained healthy through a delayed stability poll,
  and has zero restarts and no OOM kill. Caddy was not recreated and also has zero restarts/OOM.
- Heartbeat age remained below 15 seconds; idle memory was approximately 34 MiB of the 2 GiB limit.
- Live SQLite remains at schema 17 with integrity `ok`, zero foreign-key violations, and every
  pre-deployment business/audit count preserved.
- Live config remains valid: inventory routing is `agentic`; price routing remains `owner_canary`
  and unqualified with its existing live gates unchanged.
- Telegram Bot API `getMe` and all 11 configured commands succeeded. Public `/healthz` returned 200
  and `ok`; Booking.com returned 202; the configured Anthropic account listed Sonnet 5.
- Release-window and delayed logs contain no error, warning, exception, failure, or traceback.
- The idle BookSaver container contains no Chromium process and publishes no host ports directly;
  only expected SSH, DNS, HTTP, and HTTPS listeners were present.

## User acceptance

The owner should now run `/bookings` in Telegram to exercise the authenticated Stagehand inventory
path, then `/checknow` for a positively observed eligible booking. Automated deployment verification
did not impersonate a Telegram user, consume an authenticated session, or start a second
coordinator.

## Rollback readiness

- Previous image tag: `booksaver-agent:rollback-37e54b2-pre-88eeac7`.
- Pre-deployment schema-17 database backup: `/data/booksaver.db.pre-88eeac7` inside the BookSaver
  data volume.
- Operator backups: `config.toml.pre-88eeac7` and `.env.pre-88eeac7` in
  `/opt/booksaver-agent`.

This release does not change the database schema or routing configuration. Image rollback requires
retagging the saved rollback image as `booksaver-agent:latest` and recreating only BookSaver.
Restoring the database backup would discard post-deployment state and requires separate explicit
data-loss approval.
