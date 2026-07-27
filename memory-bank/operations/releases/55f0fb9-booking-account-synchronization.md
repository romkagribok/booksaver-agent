# Release 55f0fb9 — Booking.com account synchronization

## Release identity

- Released at: `2026-07-27T18:31:55Z`
- Environment: owner-operated production VPS (hostname redacted)
- Source: `main` at `55f0fb988443456460839d50e2152dcdb75c0c4b`
- Previous deployed source before this release sequence: `93a6c61`
- GitHub delivery: issue #8, PRs #9, #10, and #11
- Release scope: replace manually registered bookings with a real-time Booking.com account
  inventory; retire booking mutation/rebook commands; support the current authenticated
  `/mytrips` interface and confirmation data

## Build evidence

- Local quality gate: `962 passed in 13.06s`, Ruff clean, mypy clean across 97 source files,
  AI-DLC artifact/status validators clean, and `git diff --check` clean.
- Browser adapter gate: 14 fixture-backed tests.
- Exact staged image: `booksaver-agent:staging-55f0fb9`
- Staging image ID:
  `sha256:53b11cf6741808316e365c29b8d6f5f687f07d8cc7f48456809d2cb5559896ca`
- Staging image size: 624,220,385 bytes.
- Isolated authenticated staging acceptance completed both available Booking.com sessions:
  complete inventories of one and three reservations, with every required monitoring fact present.

## Deployment record

The VPS checkout was fast-forwarded to the merge SHA while preserving existing untracked operator
files. Online SQLite backups were taken before schema-v11 deployment and before each final image
promotion. The exact staged image was promoted to `booksaver-agent:latest`, and the production
stack was recreated with the `remote-auth` Compose profile.

Schema v11 removed unused legacy booking/check/rebook state while preserving users and encrypted
Booking.com sessions. Automatic startup synchronization then rebuilt the authoritative account
inventory and eligible monitoring projections.

## Production verification

- Active BookSaver image exactly matches the staged image ID.
- `booksaver`: healthy, zero restarts, and not OOM-killed.
- `booksaver-caddy`: running, zero restarts, and not OOM-killed.
- Public `/healthz`: HTTP 200 with body `ok`.
- TLS: valid certificate for the configured hostname through 2026-10-18.
- Public listeners: SSH plus TCP 80/443; internal application/viewer ports are not host-published.
- Database integrity: `ok`; schema version 11; foreign-key check empty.
- Users: 3 preserved; encrypted Booking.com sessions: 2 preserved.
- Startup synchronization: both sessions completed without failure, discovering four reservations.
- Eligibility projection: two eligible active reservations; two visible ineligible reservations
  with past/completed and non-refundable reasons as applicable.
- Monitoring projection: two bookings; legacy check history remains empty after the approved cutover.
- Daemon heartbeat was fresh and the release-window log error count was zero.
- Telegram command menus were verified in default, all-private-chat, and owner-chat scopes. The
  retired `/register`, `/editbooking`, `/deletebooking`, and `/rebook` commands are absent.
- Approximately 6.8 GiB remained available on the root filesystem.

## User acceptance

Use an admitted Telegram account to:

1. Run `/bookings` and confirm all four current account reservations are shown, including the two
   ineligible reservations and their reasons.
2. Run `/checknow` and confirm only an eligible reservation can be selected and checked.
3. Confirm `/register`, `/editbooking`, `/deletebooking`, and `/rebook` are absent from the Telegram
   menu and are treated as unknown if typed.
4. Change a reservation in Booking.com, run `/bookings` again, and confirm the synchronized view
   updates without any local edit workflow.

## Rollback readiness

- Pre-cutover image tag: `booksaver-agent:rollback-93a6c61`
- Pre-cutover schema-v10 backup: `/data/booksaver.db.pre-b38fb98`
- Pre-hotfix schema-v11 backup: `/data/booksaver.db.pre-819ed5c`
- Final pre-menu-deployment backup: `/data/booksaver.db.pre-55f0fb9`
- Operator configuration/environment backups: `.pre-b38fb98` files in `/opt/booksaver-agent`

Rolling back to the pre-cutover image also requires restoring the schema-v10 backup and explicitly
accepting loss of all post-cutover synchronization state. A rollback within schema v11 can use the
pre-hotfix or pre-menu backup without returning to the legacy booking model.

## Security follow-up

During release diagnostics, live application credentials and Booking.com session-linked data were
exposed to the operator's Codex conversation output. Rotate the Telegram bot token and LLM API key,
reconnect the affected Booking.com accounts, and plan a controlled application encryption-key
rotation that re-encrypts or replaces dependent local secrets rather than invalidating them
silently.
