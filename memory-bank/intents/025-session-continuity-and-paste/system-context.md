---
intent: 025-session-continuity-and-paste
status: construction
created: "2026-09-20T20:04:41Z"
---

# System context

Two independent units share the existing BookSaver control plane. Session maintenance uses the existing scheduler, encrypted per-user vault, code-owned Booking.com authentication verifier and sole coordinator/browser lease. Paste changes only the token-authorized remote viewer input path; it never handles cookies or maintenance scheduling. No new service or dependency. Booking.com remains the authority on session acceptance. The user explicitly approved scoped routine lifecycle checkpoints through merge/deploy; native Telegram checks remain distinct from automated tests.
