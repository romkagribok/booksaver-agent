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
