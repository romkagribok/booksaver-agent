# Release 0c59a7f — authentication boundary hardening

## Release identity

- Released at: `2026-07-26T21:46:38Z`
- Environment: owner-operated production VPS (hostname redacted)
- Source: `main` at `0c59a7f28358304896c3b9bd6c5708f24e4a3e97`
- Previous deployed source: `4b20aa6452b58e8e1ef4c19ef00c159113132e29`
- Release scope: complete non-owner purge across remote-auth attempts, encrypted sessions, and
  SQLite; permanently prevent post-purge session recreation; restrict `/connect` document
  navigation to Booking.com; and guide users to direct Booking.com credentials

## Build evidence

- Local quality gate: `883 passed`, Ruff clean, mypy clean across 93 source files, both AI-DLC
  validators clean, `git diff --check` clean, and two independent final reviews with no actionable
  findings.
- Focused authentication-boundary gate: `92 passed`.
- VPS staging image: `booksaver-agent:staging-0c59a7f`
- Staging image ID:
  `sha256:228dff321c0d99e11b7c0d9046579d84ecef6d6c6fa61db285a1d062d27e194c`
- Staging image size: 624,125,798 bytes.
- Staging smoke checks passed for Xvfb, x11vnc, websockify, noVNC assets, runtime imports, the CLI
  entrypoint, the Booking-only hostname predicate, production-config validation, Compose
  rendering, and Caddy configuration validation.

## Deployment record

The VPS checkout was fast-forwarded to the release SHA while preserving its existing untracked
operator files. The current production image was tagged `booksaver-agent:rollback-4b20aa6`, the
staged image was promoted to `booksaver-agent:latest`, and the production stack was recreated with
the `remote-auth` Compose profile.

The persistent configuration, environment, SQLite volume, bookings, checks, savings, and encrypted
sessions were preserved. This release adds no database migration or configuration key. Confirmed
future user purges may add a non-secret per-local-user revocation marker beside encrypted session
storage so a racing operator import cannot recreate authentication data.

## Production verification

- Active BookSaver container image exactly matches the staged image ID.
- `booksaver`: healthy, zero restarts, and not OOM-killed.
- `booksaver-caddy`: running, zero restarts, and not OOM-killed.
- Public `/healthz`: HTTP 200 with body `ok`.
- TLS: valid Let's Encrypt certificate for the configured hostname through 2026-10-18.
- Public listeners: SSH plus TCP 80/443; gateway and VNC ports are not host-published.
- Production configuration validates with the existing 12-hour interval and `/data` directory.
- Database integrity: `ok`; maximum schema version: 10.
- Daemon heartbeat: fresh after restart.
- Startup logs: Telegram bot gateway and remote-auth gateway enabled, with no startup error.
- A first scheduler tick briefly used Chromium and then cleaned it up. The settled BookSaver
  process used approximately 135 MiB, five processes, and negligible CPU; Caddy used approximately
  19 MiB.
- Approximately 6.1 GiB remained available on the root filesystem after retaining staged and
  rollback images.

## Remaining Telegram acceptance

Use a real admitted Telegram account to:

1. Send `/connect` and confirm the launch and viewer both instruct direct Booking.com
   email/password login.
2. Confirm direct Booking.com login still completes and `/status` reports the authenticated
   session.
3. Confirm selecting Google, Apple, or another external provider cannot load its page.
4. With a disposable non-owner test user only, confirm `/admin purge` names the encrypted session,
   requires explicit confirmation, removes the user, and requires a new identity/session if that
   person is invited again.

## Rollback readiness

- Previous image tag: `booksaver-agent:rollback-4b20aa6`
- Operator config backup: `/opt/booksaver-agent/config.toml.pre-0c59a7f`
- Environment backup: `/opt/booksaver-agent/.env.pre-0c59a7f`
- SQLite online backup: `/data/booksaver.db.pre-0c59a7f`

Rollback requires retagging `booksaver-agent:rollback-4b20aa6` as `booksaver-agent:latest` and
recreating the production stack with the `remote-auth` profile. Do not restore the SQLite backup
after users have performed new actions unless loss of that post-deployment state is explicitly
accepted.
