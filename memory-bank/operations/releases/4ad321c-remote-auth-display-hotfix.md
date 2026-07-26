# Release 4ad321c — remote-auth display reliability

## Release identity

- Released at: `2026-07-26T18:32:24Z`
- Environment: owner-operated production VPS (hostname redacted)
- Source: `main` at `4ad321c254879f3ebda1f42ab89d0ba57717dda7`
- Previous deployed source: `9bce54bdef1bad0519b3fa9cfa8daa3216e2ec43`
- Release scope: allow noVNC's compressed framebuffer images through the remote-auth page CSP and
  show safe, actionable viewer connection failures

## Build evidence

- Local quality gate: `871 passed`, Ruff clean, mypy clean across 93 source files, generated
  JavaScript syntax clean, AI-DLC artifact validation clean, status integrity clean, and
  `git diff --check` clean.
- VPS staging image: `booksaver-agent:staging-4ad321c`
- Staging image ID:
  `sha256:e53e4819aae79a94f4b752a40ae2cb9d8bac90a5b6a1e11f53b44ab2a4c786bc`
- Staging image size: 624,132,258 bytes
- Staging smoke checks passed for Xvfb, x11vnc, websockify, noVNC assets, remote-auth runtime
  imports, the CLI entrypoint, production-config validation, Compose rendering, and Caddy
  configuration validation.
- An in-image HTTP application check verified that `/connect/<token>` emits `img-src data:`,
  excludes `img-src 'none'`, wires the noVNC connection events, and serves the packaged
  `/novnc/core/rfb.js` asset.

## Deployment record

The VPS repository was fast-forwarded to the release SHA. The staging image was promoted to
`booksaver-agent:latest`, and the production stack was recreated with the `remote-auth` Compose
profile. Caddy remained the only public application edge; ports 8080 and 6080 remained
Compose-internal. The persistent SQLite volume and bind-mounted production configuration were
preserved.

This release did not change configuration, database schema, Telegram commands, stored bookings,
or per-user sessions.

## Production verification

- `booksaver`: healthy, zero restarts, and not OOM-killed
- `booksaver-caddy`: running
- Active image ID exactly matches the staged image ID
- Public `/healthz`: HTTP/2 200 with body `ok`
- Public bootstrap response: HTTP/2 200, `Cache-Control: no-store`, frame denial, no-referrer
  policy, and the intended `img-src data:` CSP
- Public `/novnc/core/rfb.js`: HTTP 200 with the packaged 122,518-byte asset
- TLS: valid Let's Encrypt certificate for the configured hostname through 2026-10-18
- Public listeners: SSH plus TCP 80/443; gateway and VNC ports are not host-published
- Database migrations: `schema_meta` contains versions 8, 9, and 10
- Daemon heartbeat: fresh after restart
- Startup logs: Telegram bot gateway and remote-auth gateway enabled, with no current BookSaver
  startup error
- Post-deployment resources: approximately 25 MiB for BookSaver and 17 MiB for Caddy; 8.4 GiB
  remained available on the root filesystem

The remaining acceptance check requires a real Telegram WebView: run `/connect` on mobile and
desktop, confirm that the Booking.com browser framebuffer renders instead of a gray screen, and
complete one login.

## Rollback readiness

- Previous image tag: `booksaver-agent:rollback-9bce54b`
- Operator config backup: `/opt/booksaver-agent/config.toml.pre-4ad321c`
- Environment backup: `/opt/booksaver-agent/.env.pre-4ad321c`
- SQLite online backup: `/data/booksaver.db.pre-4ad321c`

Rollback requires retagging `booksaver-agent:rollback-9bce54b` as
`booksaver-agent:latest` and recreating the production stack with the `remote-auth` profile.
Do not restore the SQLite backup after users have performed new actions unless loss of that
post-deployment state is explicitly accepted.
