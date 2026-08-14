# Release b2dd893 — remote-auth DOM recovery

## Release identity

- Released at: `2026-08-14T02:48:44Z`
- Environment: owner-operated production VPS (hostname redacted)
- Source and runtime source: `main` at `b2dd8933d506e0d2e219e8bb64e1b7f2438d91a0`
- Previous deployed source: `bfe924dc8c47ff5895b1cc9db2a4899cc7ff109e`
- GitHub delivery: PR #22
- Release scope: stop the streamed Booking.com authentication loop after `/mytrips` DOM drift;
  admit bounded grounded Sonnet recovery after the one fixed read-only probe; preserve Opus as
  diagnosis-only; and require a fresh code-issued verification receipt before cookie capture.

## Build and staging evidence

- Local release gate: 1,539 tests passed, Ruff clean, strict mypy clean across 117 source files,
  CLI smoke clean, AI-DLC integrity clean across 45 bolts and 22 intents, and `git diff --check`
  clean.
- Exact staged runtime image: `booksaver-agent:staging-b2dd893`.
- Staging/production image ID:
  `sha256:4c0f6082237b9ab42bc2954a3e15fad5406f3688726dbb6f722ac51224c68fb7`.
- Image size: 633,054,159 bytes; its OCI revision label exactly matches the merge SHA.
- A runtime-UID-writable online clone of the live schema-15 database passed integrity and
  foreign-key checks with all business aggregates unchanged.
- Persisted staging qualification under `browser-recovery-v4` passed the production-duty matrix:
  Sonnet primary recovery 50/50 with 50/50 valid schemas, Opus terminal diagnosis 10/10 with 10/10
  valid schemas, and zero prohibited executions for both profiles.

## Deployment record

The previous image was tagged `booksaver-agent:rollback-bfe924d-pre-b2dd893`. Production
`config.toml`, `.env`, and an online SQLite backup were preserved before promotion. The database
backup passed integrity and foreign-key checks at schema 15 with the release baseline aggregates.

The VPS checkout was fast-forwarded to the merge SHA while preserving untracked operator files.
Only the BookSaver container was stopped for the live model-qualification gate; Caddy stayed
running. The production ledger independently passed Sonnet 50/50 and Opus 10/10 with zero
prohibited executions in 100 fully reconciled attempts, charging 696,135 microUSD and leaving no
reserved spend.

The exact staged runtime image was promoted to `booksaver-agent:latest`, and only BookSaver was
recreated. The disposable cloned database and staging image tag were deleted after verification;
the rollback image and production backups remain.

## Production verification

- Active checkout, image label, and BookSaver image all resolve to merge `b2dd893` and the exact
  staged image ID.
- `booksaver`: healthy after three polls, zero restarts, and not OOM-killed.
- `booksaver-caddy`: continuously running since before this deployment, zero restarts, and not
  OOM-killed.
- Live Compose and Caddy configurations are valid; persisted Sonnet 5 and Opus 5 corpus-v4
  qualification is valid.
- Database schema 15, integrity `ok`, zero foreign-key violations, and pre-deployment business
  aggregates preserved: three users, four account reservations, two monitoring bookings, 20
  check-history rows, 20 check traces, 135 scheduled slots, and 124 synchronization runs.
- Release-window application logs contain only normal Telegram gateway, remote-auth gateway, and
  daemon startup lines; no error, exception, or traceback was emitted.
- Telegram Bot API `getMe` and `getMyCommands` succeeded, including `/status`, `/bookings`,
  `/checknow`, and `/connect`; Booking.com HTTPS was reachable from the container.
- Public `/healthz` returned `ok`; Caddy configuration is valid; TLS is valid through
  `2026-10-18T23:31:46Z`.
- Only SSH and TCP 80/443 listen publicly. Immediate resources were approximately 31 MiB for
  BookSaver and 17 MiB for Caddy, with 14 GiB free on the VPS root filesystem.
- No startup browser burst occurred; the container held only its normal two processes after
  promotion.

## User acceptance

The operator should now run `/connect` and finish Booking.com sign-in in the streamed browser. The
expected result is one bounded read-only probe followed by deterministic or grounded Sonnet
verification, cookie capture, and a successful Telegram connection response without repeated page
reloads. Then run `/status`, `/bookings`, and `/checknow`.

Automated verification did not impersonate a Telegram user or start a second browser coordinator.
If the authenticated inventory structure is still not safely grounded, the expected behavior is an
exact diagnosis and owner-visible maintenance incident, not an infinite reload or model-authorized
cookie capture.

## Rollback readiness

- Previous image tag: `booksaver-agent:rollback-bfe924d-pre-b2dd893`.
- Pre-deployment schema-15 database backup: `/data/booksaver.db.pre-b2dd893`.
- Operator backups: `config.toml.pre-b2dd893` and `.env.pre-b2dd893` in
  `/opt/booksaver-agent`.

The release does not change the database schema, so the saved previous image can be retagged as
`latest` and only BookSaver recreated. Restoring the pre-deployment database backup would discard
post-deployment state and the live qualification records and therefore requires separate explicit
data-loss approval.
