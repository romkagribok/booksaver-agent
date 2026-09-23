---
id: 001-resume-connect-after-leaving
unit: 003-remote-login-resume
intent: 025-session-continuity-and-paste
status: complete
priority: must
created: "2026-09-23T14:41:37Z"
assigned_bolt: 081-remote-login-resume
implemented: true
---

# US-201: Resume /connect after leaving for a code

As a user, when I leave the streamed login to fetch a verification code and come back, I want the
same login page waiting for me, so that I do not have to start /connect again.

## Acceptance criteria

- Reopening the launch link as the same Telegram user while the login is alive resumes it; the
  previous viewer session is revoked; other users are still denied.
- Leaving the page detaches for a three-minute grace instead of cancelling; returning within it
  resumes the same remote browser; Cancel still ends it immediately.
- If the user never returns, the login closes after the grace with a clear Telegram message.
- Viewer activity keeps a full session window ahead of the deadline, bounded at thirty minutes
  from creation; the remote browser honours the live deadline.
- A reloaded page resumes with its cookie without a new exchange; returning to the page polls
  immediately and re-arms one automatic stream reconnect.
