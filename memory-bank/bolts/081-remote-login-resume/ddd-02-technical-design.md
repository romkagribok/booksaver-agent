---
stage: design
bolt: 081-remote-login-resume
created: 2026-09-23T14:41:37Z
---

# Technical design

- `application/remote_auth.py`: `exchange` no longer consumes the launch digest; it revokes
  the prior viewer digest, clears `detached_at`, extends the deadline and keeps the first
  exchange's login device. `viewer_state` clears `detached_at` and extends. New `detach`
  records the first `detached_at`. `_expire_locked` closes detached attempts after
  `DETACH_GRACE` (CANCELLED, `closed_after_detach`) before ordinary expiry. `_extend_locked`
  implements the sliding deadline under `ATTEMPT_LIFETIME_CEILING`. `RemoteBrowserWork` gains
  an optional live `deadline` callable and `expired(now)`; the manager passes the attempt's
  current deadline. Viewer and Telegram messages explain a grace closure.
- `infrastructure/remote_auth/browser_runner.py`: both expiry checks use `work.expired`.
- `infrastructure/remote_auth/gateway.py`: `POST /api/connect/detach` (same origin + cookie).
- `infrastructure/remote_auth/viewer.py`: `start` tries the existing viewer session before the
  exchange; `pagehide` detaches (keepalive) instead of cancelling; `pageshow`/visible
  `visibilitychange` poll immediately and re-arm reconnection; a stable connection (≥ 5 s)
  re-arms one automatic reconnect so a flapping link stays bounded.
- `infrastructure/telegram/connect_command.py`: the link message says the user may leave to
  fetch a code and reopen it within a few minutes.
