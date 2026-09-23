---
stage: test
bolt: 081-remote-login-resume
created: "2026-09-23T14:41:37Z"
status: complete
---

# Resumable remote login verification

Manager: owner reopen mints a new viewer and revokes the old, other users denied, browser not
resized or duplicated; detach then return within grace keeps the login and clears the timer;
detach without return closes after grace with the explanatory Telegram message and the link no
longer works; explicit Cancel still ends a detached login at once; activity slides expiry to a
full window and stops at the 30-minute ceiling, with the runner's live deadline honoured.
Gateway: detach route requires same origin and cookie, never echoes it; bootstrap wires detach,
pageshow/visibility resume and session-first start. Browser: pagehide detaches and never cancels,
Cancel still cancels; returning polls immediately and reconnects after a bounded flapping link;
a reloaded page resumes with its cookie and no second exchange. Existing cancel/replacement,
finalizing and incident tests still pass. Full-gate and packaged-stack evidence appended below.

## 2026-09-23T14:55:14Z — review corrections (Cursor Bugbot, PR #61)

Three valid findings were fixed before release. (1) A leftover viewer cookie could resume any
attempt, including a finished one, from a new launch: resumption is now a server-verified
`POST /api/connect/resume` bound to the launch link's live attempt, and anything else exchanges
anew. (2) The detach-grace sweep only ran on API calls, so a viewer that left and never returned
was never closed at 180 s: the browser worker's per-second deadline read now runs the sweep, so
the login closes with no further traffic. (3) A drop before the stream ever connected counted
as a stable connection, so a flapping link could reconnect without bound: stability now requires
an actual connection and resets on every drop. Regressions: manager resume binding and
worker-driven closure, gateway resume route, browser reload resume, stale-cookie non-resume,
and never-connected drop. Remaining bounded race: a session poll already in flight when the page
hides can re-attach the attempt once; it then lives no longer than the pre-existing session window.
