# Release 39dd33f — future bookings only

## Release identity

- Released at: `2026-07-27T22:21:04Z`
- Environment: owner-operated production VPS (hostname redacted)
- Source: `main` at `39dd33ff857f23572ba824aa6c663ae1eb57ed45`
- Previous deployed source: `55f0fb988443456460839d50e2152dcdb75c0c4b`
- GitHub delivery: PR #12
- Release scope: keep the complete Booking.com account history synchronized internally while
  limiting Telegram `/bookings` to future upcoming stays.

## Build and staging evidence

- Local quality gate: `963 passed in 13.65s`, Ruff clean, mypy clean across 97 source files,
  AI-DLC artifact/status validators clean, and `git diff --check` clean.
- Exact staged image: `booksaver-agent:staging-39dd33f`
- Staging image ID:
  `sha256:9fa24ef59f2adab611dde8e9bcdd3e5eaf0762b50f50b5c233457f3e2a97eb9c`
- Staging image size: 624,225,645 bytes.
- Runtime imports, production configuration, required noVNC assets, Compose rendering, and Caddy
  configuration passed before promotion.

## Deployment record

The VPS checkout was fast-forwarded to the merge SHA while preserving untracked operator files.
The current schema-v11 database was backed up with SQLite's online backup API and verified before
restart. The previous production image was tagged for rollback, the exact staged image was
promoted to `booksaver-agent:latest`, and only the BookSaver service was recreated under the
existing `remote-auth` profile. Caddy remained running.

## Production verification

- Active BookSaver image exactly matches the staged image ID.
- `booksaver`: healthy, zero restarts, and not OOM-killed.
- `booksaver-caddy`: running, zero restarts, and not OOM-killed.
- Public `/healthz`: HTTP 200 with body `ok`.
- TLS certificate valid through `2026-10-18T23:31:46Z`.
- Database integrity: `ok`; schema version 11; foreign-key check empty.
- Daemon heartbeat fresh; release-window log error count zero.
- Raw gateway/VNC ports 5900, 6080, and 8080 are not host-listening.
- Post-startup resources settled to approximately 5% container memory for BookSaver and less than
  1% for Caddy; approximately 7.3 GiB remained available on the root filesystem.
- A read-only offline smoke invoked the deployed `/bookings` handler for all three active users
  against production data. It rendered two future upcoming reservations and omitted two
  historical/non-upcoming reservations without sending Telegram messages or exposing reservation
  details.

## User acceptance

Run `/bookings` from an admitted Telegram account and confirm only future upcoming stays appear.
Future non-refundable or otherwise ineligible stays should remain visible with their reason.

## Rollback readiness

- Previous image tag: `booksaver-agent:rollback-55f0fb9-pre-39dd33f`
- Schema-v11 online backup: `/data/booksaver.db.pre-39dd33f`
- Operator backups: `/opt/booksaver-agent/.env.pre-39dd33f` and
  `/opt/booksaver-agent/config.toml.pre-39dd33f`

This release has no schema or configuration change. Roll back by retagging the previous image as
`booksaver-agent:latest` and recreating only the BookSaver service with the `remote-auth` profile.
The database backup is recovery evidence and does not need restoration for an ordinary image
rollback.
