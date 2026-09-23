---
intent: 025-session-continuity-and-paste
created: "2026-09-20T20:04:41Z"
---

# Units

- `001-session-continuity`: bolt `078-session-continuity`, stories US-195, US-196, US-197. No dependency on the other unit.
- `002-remote-login-paste`: bolts `079-remote-login-paste` (US-198, US-199) and `080-seamless-mobile-paste` (US-200). No dependency on the other unit.
- `003-remote-login-resume`: bolt `081-remote-login-resume`, story US-201. Depends on unit 002's viewer code.
- `004-full-width-stream`: bolt `082-full-width-stream`, story US-202. Depends on units 002/003 viewer code.
