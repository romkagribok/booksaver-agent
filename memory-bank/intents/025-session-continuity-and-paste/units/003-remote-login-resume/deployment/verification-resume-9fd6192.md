---
version: resume-9fd6192
environment: production
verified: "2026-09-23T15:04:32Z"
status: passed
---

# Verification report: resume-9fd6192

- Container running/healthy, 0 restarts, OOM false, heartbeat 10 s, image `sha256:369759b2…`.
- Startup log clean; zero warnings, errors or tracebacks.
- Only Caddy publishes 80/443; no host listeners on 8080/5900/6080; no browser/display processes
  outside a login attempt.
- `config.toml` and `.env` byte-identical to their backups; VPS checkout at merge `9239e72`.
- Behaviour to observe on a real device: leave the Mini App for a code and return within three
  minutes (same page waits); reopen the link from the chat button (resumes); stay away longer
  (Telegram message and a fresh `/connect`); Cancel still ends the login immediately.
