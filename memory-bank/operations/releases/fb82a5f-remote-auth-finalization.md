# Release fb82a5f — atomic remote-auth finalization

## Release identity

- Released at: `2026-08-15T15:40:40Z`
- Environment: owner-operated production VPS (hostname redacted)
- Source and runtime source: `main` at `fb82a5fe6b2017bcd94ea31ebe5493d8e4f364c9`
- Previous deployed source: `b2dd8933d506e0d2e219e8bb64e1b7f2438d91a0`
- GitHub delivery: PR #23
- Release scope: latch code-verified remote authentication into a visible finalizing phase;
  prevent ordinary viewer close or replacement from cancelling encrypted cookie persistence; preserve
  purge and shutdown cancellation authority; and close the Telegram Mini App only after committed
  success.

## Build and staging evidence

- Local release gate: 1,548 tests passed, Ruff clean, strict mypy clean across 117 source files,
  CLI smoke clean, AI-DLC artifact validation reported zero issues, AI-DLC status integrity reported
  zero inconsistencies, and `git diff --check` was clean.
- Exact staged runtime image: `booksaver-agent:staging-fb82a5f`.
- Staging/production image ID:
  `sha256:736c78b436c6594a3be8b6c01a73a5f1ce1f4c6d78e43012d09c42770f30d347`.
- Image size: 633,065,794 bytes; its OCI revision label exactly matches the merge SHA.
- Runtime imports, the CLI, the production configuration, headed-browser executables, and required
  noVNC assets passed staging smoke checks.
- A runtime-UID-writable online clone of the live schema-15 database passed application startup,
  persisted model qualification, integrity, and foreign-key checks with all business aggregates
  unchanged.
- No live model qualification was run because this release does not change model profiles, prompts,
  policy, qualification corpus, or schema. The persisted `browser-recovery-v4` qualification remains
  valid for Sonnet 5 primary recovery and Opus 5 terminal diagnosis.

## Deployment record

The previous image was tagged `booksaver-agent:rollback-b2dd893-pre-fb82a5f`. Production
`config.toml`, `.env`, and an online SQLite backup were preserved before promotion. The database
backup passed integrity and foreign-key checks at schema 15 with the release baseline aggregates.

The VPS checkout was fast-forwarded to the merge SHA while preserving untracked operator files.
The exact staged runtime image was promoted to `booksaver-agent:latest`, and only BookSaver was
recreated. Caddy stayed running. The disposable cloned database, staging worktree, staging image tag,
and temporary verification files were deleted after verification; the rollback image and production
backups remain.

## Production verification

- Active checkout, image label, and BookSaver image all resolve to merge `fb82a5f` and the exact
  staged image ID.
- `booksaver`: healthy, zero restarts, and not OOM-killed.
- `booksaver-caddy`: continuously running since before this deployment, zero restarts, and not
  OOM-killed.
- Live Compose and Caddy configurations are valid; persisted Sonnet 5 and Opus 5 corpus-v4
  qualification is valid.
- Database schema 15, integrity `ok`, zero foreign-key violations, and pre-deployment business
  aggregates preserved: three users, four account reservations, two monitoring bookings, 20
  check-history rows, 20 check traces, 144 scheduled slots, and 133 synchronization runs.
- The release-window application log contains four normal startup lines and no error, exception,
  critical entry, or traceback.
- Telegram Bot API `getMe` and `getMyCommands` succeeded, including `/status`, `/bookings`,
  `/checknow`, and `/connect`.
- Public `/healthz` succeeded; Caddy configuration is valid; public TLS is valid through
  `2026-10-18T23:31:46Z`.
- DNS and TLS handshakes to Booking.com, Anthropic, and Telegram succeeded from the BookSaver
  container.
- Only SSH, DNS, and TCP 80/443 listen on the VPS. Immediate resources were approximately 30 MiB
  for BookSaver and 18 MiB for Caddy, with 12 GiB free on the VPS root filesystem.
- No startup browser burst occurred; the container held only its normal two processes after
  promotion.

## User acceptance

The operator should now run `/connect` and finish Booking.com sign-in in the streamed browser. After
code verification, the viewer should enter `Authentication verified; saving...`, disconnect the
stream, ignore ordinary close/page-hide cancellation, persist encrypted cookies, report successful
connection in Telegram, and close the Mini App. Then run `/status`, `/bookings`, and `/checknow`.

Automated verification did not impersonate a Telegram user or start a second browser coordinator.
Capture rejection must produce a safe explicit failure and must not publish a false recovered-DOM
incident.

## Rollback readiness

- Previous image tag: `booksaver-agent:rollback-b2dd893-pre-fb82a5f`.
- Pre-deployment schema-15 database backup: `/data/booksaver.db.pre-fb82a5f`.
- Operator backups: `config.toml.pre-fb82a5f` and `.env.pre-fb82a5f` in
  `/opt/booksaver-agent`.

The release does not change the database schema, so the saved previous image can be retagged as
`latest` and only BookSaver recreated. Restoring the pre-deployment database backup would discard
post-deployment state and therefore requires separate explicit data-loss approval.
