---
version: paste-7995864
environment: production
verified: "2026-09-22T02:38:03Z"
status: passed
---

# Verification report: paste-7995864

- Container running/healthy, 0 restarts, OOM false, heartbeat 6 s, image `sha256:81bceb3e…`.
- Startup log clean; zero warnings, errors or tracebacks in the first minutes.
- Only Caddy publishes 80/443; no host listeners on 8080/5900/6080; no Chromium/Xvfb/x11vnc/websockify
  processes outside a login attempt.
- `config.toml` and `.env` byte-identical to their backups; VPS checkout at merge `2d57401`.
- Packaged-stack evidence for the fix: six-box auto-advance probe passes on the exact image for both
  Ctrl/Cmd+V and masked Insert; the 27-check ASCII/CapsLock/rejection probe still passes.
- Physical Telegram mobile and desktop paste remain user-observed acceptance.
