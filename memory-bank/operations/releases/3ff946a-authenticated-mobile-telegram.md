# Release 3ff946a — authenticated mobile Telegram sessions

## Release identity

- Released at: `2026-07-21T00:32:35Z`
- Environment: owner-operated production VPS `booksaver-finland`
- Source: `main` at `3ff946ac6a47f5b297b780350547d50707bfd9aa`
- Previous deployed source: `98505271624b204916edc6f7e0ea4cddc0f13aa5`
- Release scope: invite/privacy hardening, post-rebook monitoring propagation, per-user
  Booking.com sessions, Telegram remote login, and authenticated mobile-web checks

## Build evidence

- Local quality gate: `867 passed`, Ruff clean, mypy clean across 93 source files, and
  `git diff --check` clean.
- VPS staging image: `booksaver-agent:staging-3ff946a`
- Staging image ID: `sha256:f52e09d2352f75af850519605108959436c9992d4d6a892d2924a0d31c5257a6`
- Staging smoke checks passed for Xvfb, x11vnc, websockify, noVNC assets, remote-auth
  runtime imports, the CLI entrypoint, and production-config validation.

## Deployment record

The VPS repository was fast-forwarded to `main` at the release SHA. The approved mobile
browser and remote-auth configuration was installed in the persistent `/data/config.toml`:

- browser profile: `android-chromium`
- locale: `en-US`
- timezone: `America/Indiana/Indianapolis`
- remote-auth public origin: `https://static.254.91.181.135.clients.your-server.de`
- login attempt timeout: 600 seconds

The staging image was promoted to `booksaver-agent:latest`, and the production stack was
started with the `remote-auth` Compose profile. Caddy is the only public application edge;
the gateway and VNC ports remain Compose-internal. UFW allows SSH plus TCP 80/443.

The first HTTPS probe returned 502 because the daemon reads the persistent
`/data/config.toml`, while only the repository-side operator copy had initially been updated.
The validated configuration was installed into the persistent volume and BookSaver was
restarted. The next probe returned 200 and the remote-auth startup banner was present.

## Production verification

- `booksaver`: healthy
- `booksaver-caddy`: running
- Public `/healthz`: HTTP/2 200 with body `ok`
- TLS: valid Let's Encrypt certificate for the configured hostname
- Database migrations: `schema_meta` contains versions 8, 9, and 10
- Telegram command scopes: ordinary private chats include `/connect`, `/editbooking`,
  `/deletebooking`, and `/checknow`; the owner scope additionally includes `/admin`
- Startup logs: Telegram bot gateway and remote-auth gateway enabled, with no current
  BookSaver startup error

The remaining acceptance checks require a real Telegram user: completing `/connect`, viewing
the resulting caller-scoped session state, and running `/checknow` against Booking.com.

## Rollback readiness

- Previous image tag: `booksaver-agent:rollback-9850527`
- Operator config backup: `/opt/booksaver-agent/config.toml.pre-3ff946a`
- Environment backup: `/opt/booksaver-agent/.env.pre-3ff946a`
- SQLite online backup: `/data/booksaver.db.pre-3ff946a`

Do not restore the SQLite backup after users have performed new actions unless loss of that
post-deployment state is explicitly accepted. The future stronger login-isolation work remains
tracked in GitHub issue #6.
