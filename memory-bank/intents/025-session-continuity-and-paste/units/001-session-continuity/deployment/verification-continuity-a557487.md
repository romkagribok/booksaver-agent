---
version: continuity-a557487
environment: production
verified: "2026-09-22T01:42:44Z"
status: passed
---

# Verification report: continuity-a557487

Independent post-promotion checks about two minutes after start:

- Container running/healthy, **0 restarts**, OOM false, image
  `sha256:cb35711dc21eadba038f4f6fbcb82ef4b79bb4fffd76ce5d27389e93212c2700`; heartbeat 14 s old.
- Startup log clean: Telegram gateway enabled, remote authentication gateway announced, daemon
  planning without a startup burst; zero maintenance warnings, tracebacks or errors.
- Only Caddy publishes 80/443; BookSaver publishes no host ports; 8080/5900/6080 are not listening on
  the host. No Chromium, Xvfb, x11vnc or websockify processes remain.
- SQLite `quick_check` ok at schema 18; VPS checkout at merge `8956f4d`; `config.toml` and `.env`
  byte-identical to their backups. Rollback tag resolves to the previous production image.
- Live session maintenance is scheduled by the daemon (`booking_com_session_maintenance`) and will
  run on each user's daily due time; its outcome is readable afterwards from persisted session
  metadata without additional Booking.com requests. No renewal is claimed yet for production.
- Paste: packaged-stack automation only; native Telegram desktop/mobile acceptance is user-driven.
