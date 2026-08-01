# Release d8f421f — randomized daily booking checks

## Release identity

- Released at: `2026-08-01T22:01:34Z`
- Environment: owner-operated production VPS (hostname redacted)
- Source: `main` at `d8f421fbe8d8d02b04b4696a471ade93eca9999e`
- Previous deployed source: `d5c76b17de63b7acf8e39a716b602856d1f7d5d9`
- GitHub delivery: PR #16
- Release scope: replace the fixed global interval with three persisted, randomized UTC checks per
  eligible booking and day, using broad eight-hour windows, two-hour minimum spacing, and bounded
  restart catch-up.

## Build and staging evidence

- Local quality gate: `1038 passed in 10.75s`, Ruff clean, mypy clean across 100 source files,
  CLI smoke clean, AI-DLC artifact/status validators clean, and `git diff --check` clean.
- Exact staged image: `booksaver-agent:staging-d8f421f`.
- Staging/production image ID:
  `sha256:c9c45c9666e5f1930cd23a21d6622789ca9c0449465a9723dfdead19cb5215cc`.
- Staging image size: 632,489,486 bytes.
- Runtime imports, required noVNC assets, production configuration, Compose rendering, and Caddy
  validation passed before promotion.
- A clone of the production schema-v11 database migrated to v12 with integrity `ok`, no foreign-key
  violations, and unchanged aggregate counts: three users, four account reservations, two active
  monitoring bookings, and 19 check-history rows.
- The staging clone persisted three random slots for each active user and verified the two-hour
  spacing invariant.

## Deployment record

The VPS checkout was fast-forwarded to the merge SHA while preserving its existing untracked
operator files. The current image was tagged for rollback, production config and environment files
were backed up locally on the VPS, and two verified online SQLite backups were taken before schema
migration. Legacy `check_interval = "12h"` was replaced by the approved `3 / 2h / 1h` schedule
settings.

The exact staged image was promoted to `booksaver-agent:latest`. Only the BookSaver service was
recreated under the existing `remote-auth` profile; Caddy remained running. The temporary staging
database volume was removed after promotion; the original verified backups remain available.

## Production verification

- Active BookSaver image exactly matches the staged image ID.
- `booksaver`: healthy, zero restarts, and not OOM-killed.
- `booksaver-caddy`: running continuously, zero restarts, and not OOM-killed.
- Release-window application error count: zero.
- Public `/healthz`: HTTP 200 with body `ok`.
- TLS certificate valid through `2026-10-18T23:31:46Z`.
- Only SSH and TCP 80/443 are publicly listening; raw application and viewer ports remain internal.
- Database integrity: `ok`; schema version 12; foreign-key check empty; pre-deployment aggregate
  data counts preserved.
- Startup generated a two-day horizon of six slots per active user. The nine future slots contain
  exactly one random time per eight-hour window and satisfy cross-slot two-hour spacing.
- Nine same-day slots outside the one-hour grace became terminal missed slots. Check history stayed
  at 19 rows, proving the restart produced no browser-check burst.
- Daemon heartbeat was current at verification.
- Telegram Bot API connectivity and the `/status`, `/bookings`, and `/checknow` command menu passed.
- An offline production-data `/status` smoke resolved the owner's caller-scoped persisted next slot
  without exposing another user's schedule.
- Post-startup resources were approximately 26 MiB for BookSaver and 13 MiB for Caddy; 6.3 GiB
  remained available on the root filesystem.

## User acceptance

The operator was asked to run `/status` and one real `/checknow` against an eligible refundable
booking. Automated deployment verification does not impersonate a Telegram user or trigger a live
Booking.com browser check through a second coordinator. Confirm that `/status` shows a future UTC
slot and that `/checknow` completes through the authenticated mobile-web pipeline.

## Rollback readiness

- Previous image tag: `booksaver-agent:rollback-d5c76b1-pre-d8f421f`.
- Pre-deployment schema-v11 backup: `/data/booksaver.db.pre-d8f421f`.
- Final pre-promotion schema-v11 backup: `/data/booksaver.db.pre-d8f421f-final`.
- Operator configuration/environment backups: `config.toml.pre-d8f421f` and `.env.pre-d8f421f` in
  `/opt/booksaver-agent`.

An ordinary image rollback within schema v12 can retag the rollback image as `latest` and recreate
only BookSaver. Returning to the previous schema-v11 image requires stopping BookSaver and restoring
one of the verified schema-v11 backups, which would discard post-deployment schedule/check state and
therefore requires explicit data-loss acceptance.
