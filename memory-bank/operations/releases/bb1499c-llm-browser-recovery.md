# Release bb1499c — guarded LLM browser recovery

## Release identity

- Released at: `2026-08-02T20:20:35Z`
- Environment: owner-operated production VPS (hostname redacted)
- Source: `main` at `bb1499ceee3538c6794767051273c20bb2d0609b`
- Feature commit: `18fcf83765f83defdec2ec2a5950b2343f49b58b`
- Previous deployed source: `4b9331de56e78358bfff7db5ac16ea111a84d429`
- GitHub delivery: PR #18
- Release scope: harden shared Booking.com recovery and extend deterministic-first, guarded LLM
  fallback to authenticated reservation discovery used by `/bookings`, `/checknow`, scheduled
  synchronization, and post-connect refresh.

## Build and staging evidence

- Local quality gate: 1225 tests passed, Ruff clean, strict mypy clean across 103 source files,
  CLI/config smoke clean, AI-DLC artifact/status validators clean, and `git diff --check` clean.
- Independent security review closed all five release blockers and found no remaining P0/P1 issue.
- Exact staged image: `booksaver-agent:staging-bb1499c`.
- Staging/production image ID:
  `sha256:6bd264ebe5bde76e90eb223abd38386f7fd9763cf3f12a8a0a941ff6d9c81bbb`.
- Staging image size: 632,689,321 bytes.
- Runtime imports, packaged replay API, booking/evaluation CLI surfaces, required noVNC assets,
  production configuration, Compose rendering, and Caddy validation passed before promotion.
- A production schema-v12 clone migrated to schema v13 with integrity `ok`, no foreign-key
  violations, and unchanged aggregate counts: three users, four account reservations, two active
  monitoring bookings, 20 check-history rows, 48 synchronization runs, and 27 schedule slots.

## Deployment record

The VPS checkout was fast-forwarded to the merge SHA while preserving all untracked operator files.
The running image was tagged `booksaver-agent:rollback-4b9331d`; `config.toml`, `.env`, and an online
SQLite backup were preserved before migration. The backup passed integrity and foreign-key checks.

The exact staged image was promoted to `booksaver-agent:latest`, and only the BookSaver service was
recreated. Caddy remained running continuously and the persistent data volume remained mounted. The
temporary staging database volume was removed after production verification.

## Production verification

- Active BookSaver image exactly matches the staged image ID.
- `booksaver`: healthy, zero restarts, and not OOM-killed.
- `booksaver-caddy`: running continuously, zero restarts, and not OOM-killed.
- Database schema 13, integrity `ok`, zero foreign-key violations, and all pre-deployment aggregate
  counts preserved.
- All schema-v13 content-free recovery-audit columns are present.
- Heartbeat age was 14 seconds at verification.
- Telegram Bot API `getMe` and `getMyCommands` succeeded without exposing the token.
- Public `/healthz` returned `ok`; TLS is valid through `2026-10-18T23:31:46Z`.
- Only SSH and TCP 80/443 listen publicly; application/viewer ports remain Compose-internal.
- Release-window logs contain no application error or traceback. Startup reports the Telegram
  gateway enabled and the daemon using three randomized checks per day with two-hour spacing.
- Immediate resources: approximately 27 MiB for BookSaver and 15 MiB for Caddy; 5.1 GiB remained
  available on the root filesystem.
- The production LLM key is configured. No model or live Booking.com call was made during automated
  rollout verification.

## User acceptance

The operator should now run `/status`, `/bookings`, and `/checknow` from Telegram. `/bookings` should
either complete deterministically, recover through the guarded fallback, or preserve the prior safe
inventory with a precise partial/failure result. `/checknow` should either produce a verified result
or stop with a specific bounded recovery code rather than running to the outer timeout.

Automated deployment verification did not impersonate a Telegram user or start a second browser
coordinator. For an assisted inventory run, the operator can inspect its content-free audit with
`booksaver bookings trace <sync-run-id>` inside the container.

## Rollback readiness

- Previous image tag: `booksaver-agent:rollback-4b9331d`.
- Pre-deployment schema-v12 database backup: `/data/booksaver.db.pre-bb1499c`.
- Operator backups: `config.toml.pre-bb1499c` and `.env.pre-bb1499c` in
  `/opt/booksaver-agent`.

Schema v13 is additive, so the prior image can be retagged as `latest` and only BookSaver recreated.
Restoring the schema-v12 database backup would discard post-deployment synchronization/check state
and therefore requires separate explicit data-loss approval.
