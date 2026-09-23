---
version: resume-9fd6192
environment: production
created: "2026-09-23T15:04:32Z"
verified: "2026-09-23T15:04:32Z"
status: verified
---

# Monitoring handoff

Continue Docker health, heartbeat and protected logs. New user-facing signals: the Telegram
message "stayed closed for a few minutes, so the connection ended" marks a detach-grace closure
(expected when a user leaves and does not return); "Booking.com connection cancelled" remains an
explicit Cancel. The shared browser may stay reserved up to 180 s longer than before after a user
leaves; a busy reply to another user's `/connect` or a delayed check within that window is
expected. No new external alert or SLO.
