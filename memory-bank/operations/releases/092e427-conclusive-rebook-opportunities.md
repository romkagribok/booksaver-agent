# Release 092e427 — conclusive rebook opportunities

## Release identity

- Released at: `2026-07-27T02:55:37Z`
- Environment: owner-operated production VPS (hostname redacted)
- Source: `main` at `092e42762e199af924d5eb48421ea1b6ce30f889`
- Previous deployed source: `1a1c7a6c2944224b9c11aa94f8362171644d0dd0`
- Release scope: show at most one actionable savings opportunity per active booking, preserve the
  last verified opportunity across technical check failures, supersede it after a conclusive
  market result, and reject stale Telegram selections atomically

## Build evidence

- Local quality gate: `937 passed`, Ruff clean, mypy clean across 94 source files, both AI-DLC
  validators clean, and `git diff --check` clean.
- No dependency, database schema, or production configuration change.
- VPS staging image: `booksaver-agent:staging-092e427`
- Staging image ID:
  `sha256:a9d391112ebdda321ed37cf101aa14b8783d6129a908b8e8980586f188073615`
- Staging image size: 624,160,213 bytes.
- Staging smoke checks passed for runtime imports, CLI startup, noVNC assets, production config,
  Compose rendering, and Caddy configuration.

## Deployment record

The VPS checkout was fast-forwarded to the release SHA while preserving its existing untracked
operator files. The prior production image was tagged `booksaver-agent:rollback-1a1c7a6`, the
staged image was promoted to `booksaver-agent:latest`, and the BookSaver service was recreated
under the existing `remote-auth` Compose profile. Caddy remained running throughout.

The persistent configuration, environment, SQLite volume, bookings, checks, savings, encrypted
sessions, and append-only opportunity history were preserved.

## Production verification

- Active BookSaver container image exactly matches the staged image ID.
- `booksaver`: healthy, zero restarts, and not OOM-killed.
- `booksaver-caddy`: running, zero restarts, and not OOM-killed.
- Public `/healthz`: HTTP 200 with body `ok`, `Cache-Control: no-store`, and security headers.
- TLS: valid Let's Encrypt certificate for the configured hostname through 2026-10-18.
- Public listeners: SSH plus TCP 80/443; gateway and VNC ports are not host-published.
- Production configuration validates with the existing 12-hour interval and `/data` directory.
- Database integrity: `ok`; maximum schema version: 10.
- Daemon heartbeat: fresh after restart.
- Startup logs: Telegram bot gateway and remote-auth gateway enabled, with no startup error.
- Post-deployment resources: approximately 24 MiB for BookSaver and 11 MiB for Caddy; 11 GiB
  remained available on the root filesystem.

## Remaining Telegram acceptance

Use a real admitted Telegram account to:

1. Run `/rebook` when multiple historical positive checks exist for one booking and confirm only
   the latest conclusive opportunity is offered.
2. After a technical check failure, run `/rebook` and confirm the last successfully verified
   opportunity remains visible with its verification time.
3. After a successful check finds a smaller saving, confirm it replaces the older larger saving.
4. After a successful non-saving or `no_equivalent_offer` check, confirm the prior opportunity is
   no longer offered.
5. Tap an old Telegram callback after a conclusive newer check and confirm BookSaver rejects it
   without creating a guided rebook session.

## Rollback readiness

- Previous image tag: `booksaver-agent:rollback-1a1c7a6`
- Operator config backup: `/opt/booksaver-agent/config.toml.pre-092e427`
- Environment backup: `/opt/booksaver-agent/.env.pre-092e427`
- SQLite online backup: `/data/booksaver.db.pre-092e427`

Rollback requires retagging `booksaver-agent:rollback-1a1c7a6` as
`booksaver-agent:latest` and recreating the production stack with the `remote-auth` profile.
Do not restore the SQLite backup after users have performed new actions unless loss of that
post-deployment state is explicitly accepted.
