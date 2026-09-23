---
unit: 003-remote-login-resume
intent: 025-session-continuity-and-paste
created: "2026-09-23T14:41:37Z"
status: complete
---

# Remote login resume

Keep a `/connect` login alive while the user leaves Telegram's Mini App to fetch a verification
code, and let the same user reopen it. Owns the remote-auth manager's launch/viewer capability
lifecycle, detach grace, sliding expiry, the gateway detach route and the viewer's resume
behaviour. Depends on Bolt 079/080 viewer code; no dependency on unit 001.
