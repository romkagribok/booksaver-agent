---
stage: model
bolt: 081-remote-login-resume
created: 2026-09-23T14:41:37Z
---

# Resumable remote login model

The **remote authentication attempt** aggregate (one per user, holding the single browser gate)
gains explicit viewer presence:

- **Launch capability**: bound to one Telegram user; usable by that user until the attempt is
  terminal. Each exchange requires freshly signed launch data (replay-protected) and mints a new
  **viewer capability**, revoking the previous one. Invariant: at most one valid viewer per attempt.
- **Presence**: `attached` (viewer polling) or `detached(since)`. Leaving the page detaches;
  any poll or exchange re-attaches. A detachment older than `DETACH_GRACE` (180 s) closes the
  attempt as CANCELLED with `closed_after_detach`, which selects the user-facing explanation.
- **Deadline**: `expires_at` slides to `now + session window` on viewer activity, bounded by
  `created_at + ATTEMPT_LIFETIME_CEILING` (1800 s). The browser worker reads the live deadline.

Unchanged: STARTING → READY → CONNECTED → FINALIZING → terminal transitions, explicit Cancel,
same-user replacement, administrative cancellation, capture rules and credential blindness.
