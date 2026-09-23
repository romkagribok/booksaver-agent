---
version: seamless-f2bb781
environment: production
verified: "2026-09-23T00:46:55Z"
status: passed
---

# Verification report: seamless-f2bb781

- Container running/healthy, 0 restarts, OOM false, heartbeat 3 s, image `sha256:c57ca980…`.
- Startup log clean; zero warnings, errors or tracebacks in the first minutes.
- Only Caddy publishes 80/443; no host listeners on 8080/5900/6080; no Chromium/Xvfb/x11vnc/websockify
  processes outside a login attempt.
- `config.toml` and `.env` byte-identical to their backups; VPS checkout at merge `4986db1`.
- Packaged-stack evidence on the exact image: 31 ASCII checks and the six-box probe on five paths.
- Physical Telegram mobile and desktop paste remain user-observed acceptance: browser read where
  permitted, otherwise a keyboard suggestion/chip or long-press Paste; never an Insert tap for
  pasted text.
