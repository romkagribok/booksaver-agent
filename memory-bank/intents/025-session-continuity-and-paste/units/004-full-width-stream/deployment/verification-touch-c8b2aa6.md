---
version: touch-c8b2aa6
environment: production
verified: "2026-09-23T19:34:36Z"
status: passed
---

# Verification report: touch-c8b2aa6

- Container running/healthy, 0 restarts, OOM false, heartbeat 5 s, image `sha256:e1e0965f…`.
- Clean startup log; only Caddy publishes 80/443; no private host listeners; no orphan
  browser/display processes.
- `config.toml` and `.env` byte-identical to backups; VPS checkout at merge `9936499`.
- To observe: no arrow cursor on phone or iPad; iPad renders the page at tablet width.
