# Release bfe924d — adaptive DOM resilience

## Release identity

- Released at: `2026-08-13T14:10:55Z`
- Environment: owner-operated production VPS (hostname redacted)
- Source: `main` at `bfe924dc8c47ff5895b1cc9db2a4899cc7ff109e`
- Runtime source: `14c7fa92882b3f99783de9eaba26d892a2627a5d`; the later feature commits contain
  only AI-DLC qualification evidence.
- Previous deployed source: `c456a229b1347377e8504a4dae17b59036ab5e72`
- GitHub delivery: PR #21
- Release scope: deterministic-first Booking.com DOM resilience with fixed Sonnet 5 primary
  recovery, diagnosis-only Opus 5 escalation, exact job/day cost admission, typed terminal reasons,
  and owner-only encrypted DOM-drift incident operations.

## Build and staging evidence

- Local release gate: 1,525 tests passed, Ruff clean, strict mypy clean across 117 source files,
  CLI smoke clean, AI-DLC integrity clean across 44 bolts and 22 intents, and `git diff --check`
  clean.
- Exact staged runtime image: `booksaver-agent:staging-14c7fa9`.
- Staging/production image ID:
  `sha256:5c859dce25218090b7566149554aefc57e95537decba748ccad851c28f58dee5`.
- Image size: 633,020,514 bytes.
- A runtime-UID-writable online clone of the production schema-v13 database migrated to schema 15
  with integrity `ok`, no foreign-key violations, and unchanged aggregates.
- Persisted staging qualification under `browser-recovery-v4` passed the production-duty matrix:
  Sonnet primary recovery 50/50 with 50/50 valid schemas, Opus terminal diagnosis 10/10 with 10/10
  valid schemas, and zero prohibited executions for both profiles.

## Deployment record

The running image was tagged `booksaver-agent:rollback-c456a22-pre-bfe924d`. Production
`config.toml`, `.env`, and an online SQLite backup were preserved before migration. The SQLite
backup passed integrity and foreign-key checks at schema 13 with all release baseline aggregates.

The VPS checkout was fast-forwarded to the merge SHA while preserving untracked operator files.
Only the BookSaver container was stopped for live schema migration and qualification; Caddy stayed
running. The live database migrated additively to schema 15 with all baseline counts unchanged.
The production ledger then independently passed Sonnet 50/50 and Opus 10/10 with zero prohibited
executions at approximately 691,530 microUSD estimated cost.

The exact staged runtime image was promoted to `booksaver-agent:latest`, and only BookSaver was
recreated. Temporary staging worktrees, image tags, and the cloned staging database were deleted
after production verification. The active image and two rollback generations remain; root disk
availability increased to 17 GiB.

## Production verification

- Active checkout is merge `bfe924d`; active BookSaver image exactly matches the staged image ID
  and runtime revision `14c7fa9`.
- `booksaver`: healthy on first poll, zero restarts, and not OOM-killed.
- `booksaver-caddy`: continuously running, zero restarts, and not OOM-killed.
- Live configuration is valid; persisted Sonnet 5 and Opus 5 corpus-v4 qualification is valid.
- Database schema 15, integrity `ok`, zero foreign-key violations, and all pre-deployment aggregates
  preserved: three users, four account reservations, two monitoring bookings, 20 check-history
  rows, 20 check traces, 126 scheduled slots, and 121 synchronization runs.
- Release-window application logs contain only normal Telegram gateway, remote-auth gateway, and
  daemon startup lines; no error or traceback was emitted.
- Telegram Bot API `getMe` and `getMyCommands` succeeded, and the menu includes `/status`,
  `/bookings`, and `/checknow`.
- Public `/healthz` returned `ok`; Caddy configuration is valid; TLS is valid through
  `2026-10-18T23:31:46Z`.
- Only SSH and TCP 80/443 listen publicly. Telegram, Anthropic, and Booking.com endpoints were
  reachable from the VPS.
- Immediate resources were approximately 28 MiB for BookSaver and 20 MiB for Caddy.
- Scheduled-slot, check-history, and synchronization aggregates did not show a startup browser
  burst.

## User acceptance

The operator should now run `/status`, `/bookings`, and `/checknow` from Telegram. Automated
deployment verification did not impersonate a Telegram user or start a second browser coordinator.
If Booking.com DOM drift is encountered, the expected behavior is a verified recovery or an exact
typed stop; genuinely ambiguous unresolved drift should produce an owner-only incident and
maintenance notice rather than a generic navigation failure.

## Rollback readiness

- Previous image tag: `booksaver-agent:rollback-c456a22-pre-bfe924d`.
- Older rollback generation: `booksaver-agent:rollback-623b88a-pre-c456a22`.
- Pre-deployment schema-v13 database backup: `/data/booksaver.db.pre-bfe924d`.
- Operator backups: `config.toml.pre-bfe924d` and `.env.pre-bfe924d` in
  `/opt/booksaver-agent`.

Schema 14/15 migrations are additive, so the saved previous image can be retagged as `latest` and
only BookSaver recreated. Restoring the schema-v13 database backup would discard post-deployment
state and therefore requires separate explicit data-loss approval.
