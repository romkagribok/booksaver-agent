# Release 52757c4 — device-aware remote-auth recovery

## Release identity

- Released at: `2026-07-26T23:21:50Z`
- Environment: owner-operated production VPS (hostname redacted)
- Source: `main` at `52757c46fbfcd90d0ad645f535c60ef984047376`
- Previous deployed source: `0af7340026b3a10b4d92e681ccb3d67b0f1249b5`
- Release scope: make the Telegram remote-auth viewer usable on touch devices, present Booking.com
  without desktop browser chrome, and immediately release abandoned same-user login attempts

## Build evidence

- Local quality gate: `898 passed`, Ruff clean, mypy clean across 93 source files, both AI-DLC
  validators clean, `git diff --check` clean, and independent final reviews with no actionable
  findings.
- Focused remote-auth gate: `36 passed`.
- VPS staging image: `booksaver-agent:staging-52757c4`
- Staging image ID:
  `sha256:03ecf729dfbf6a1263d06bb83f37f802e08d1cbd80ef9c8519ccaa75e30ec137`
- Staging image size: 624,133,827 bytes.
- Staging smoke checks passed for Xvfb, x11vnc, websockify, the required noVNC RFB, keyboard, and
  keysym modules, remote-auth runtime imports, kiosk Chromium arguments, production-config
  validation, Compose rendering, and Caddy configuration validation.

## Deployment record

The VPS checkout was fast-forwarded to the release SHA while preserving its existing untracked
operator files. The prior production image was tagged `booksaver-agent:rollback-0af7340`, the
staged image was promoted to `booksaver-agent:latest`, and the production stack was recreated with
the `remote-auth` Compose profile.

The persistent configuration, environment, SQLite volume, bookings, checks, savings, and encrypted
sessions were preserved. This release adds no database migration or configuration key.

## Production verification

- Active BookSaver container image exactly matches the staged image ID.
- `booksaver`: healthy, zero restarts, and not OOM-killed.
- `booksaver-caddy`: running, zero restarts, and not OOM-killed.
- Public `/healthz`: HTTP 200 with body `ok`.
- Public viewer probe: HTTP 200 with `Cache-Control: no-store`, a content security policy, the
  password-semantic mobile keyboard bridge, page-close abandonment handling, and the packaged
  noVNC keyboard/keysym imports.
- Public noVNC keyboard asset: HTTP 200.
- TLS: valid Let's Encrypt certificate for the configured hostname through 2026-10-18.
- Public listeners: SSH plus TCP 80/443; gateway and VNC ports are not host-published.
- Production configuration validates with the existing 12-hour interval and `/data` directory.
- Database integrity: `ok`; maximum schema version: 10.
- Daemon heartbeat: fresh after restart.
- Startup logs: Telegram bot gateway and remote-auth gateway enabled, with no startup error.
- Post-deployment resources: approximately 242 MiB for BookSaver and 13 MiB for Caddy; 6.1 GiB
  remained available on the root filesystem.

## Remaining Telegram acceptance

Use a real admitted Telegram account to:

1. Open `/connect` on Android or iOS and confirm Booking.com fills the viewer without desktop
   browser chrome.
2. Tap the remote email/password fields, open the viewer keyboard, and verify typing, Unicode,
   Backspace, Next/Tab, Enter, and Hide/Show.
3. Close the viewer without pressing Cancel, immediately send `/connect` again, and confirm the
   replacement login opens instead of reporting another active login.
4. Complete a direct Booking.com email/password login and confirm `/status` reports the
   authenticated session.
5. Repeat `/connect` on Telegram Desktop as a regression check.

External identity-provider login remains intentionally blocked; use direct Booking.com credentials.

## Rollback readiness

- Previous image tag: `booksaver-agent:rollback-0af7340`
- Operator config backup: `/opt/booksaver-agent/config.toml.pre-52757c4`
- Environment backup: `/opt/booksaver-agent/.env.pre-52757c4`
- SQLite online backup: `/data/booksaver.db.pre-52757c4`

Rollback requires retagging `booksaver-agent:rollback-0af7340` as
`booksaver-agent:latest` and recreating the production stack with the `remote-auth` profile.
Do not restore the SQLite backup after users have performed new actions unless loss of that
post-deployment state is explicitly accepted.
