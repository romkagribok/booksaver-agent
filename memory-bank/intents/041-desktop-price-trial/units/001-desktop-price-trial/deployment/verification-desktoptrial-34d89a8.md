---
version: desktoptrial-34d89a8
environment: production
verified: "2026-11-13T13:22:40Z"
created: "2026-11-13T03:27:17Z"
status: passed
---

# Production verification

- Promotion: healthy, no restarts, schema 25, internal and public health passed, Caddy unchanged,
  no host port published.
- Trial wiring in the running container: executor built; active for user 4, not for user 1;
  `desktop_trial_readings` empty.
- Read-back of the first trial slot (2026-11-13 12:36Z): four readings, one per checked booking;
  Ayres USD 146 and AIRINN EUR 157 on both mobile and desktop; Park Plaza and Kalipè failed the
  same way on both. No history, savings, alert or session write from a reading; no
  `auth_required` or `bot_wall`; container healthy with no restarts.
