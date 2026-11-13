---
version: desktoptrial-34d89a8
environment: production
created: "2026-11-13T03:27:17Z"
verified: "2026-11-13T03:27:17Z"
status: verified
---

# Monitoring handoff

- After each user 4 slot, `desktop_trial_readings` gains one row per booking the slot checked,
  and `jev_price_runs` one `jev-price-desktop-trial` row per reading.
- User 4's mobile checks must look as they did before: no new `auth_required`, no `bot_wall`.
  Either one, or a sign-in request to him, means stop: set `[desktop_trial] user_ids = []` and
  recreate the container.
- No reading on or after 2026-11-20.

Pairs for the evaluation:

```sql
SELECT r.observed_at, h.outcome, h.live_amount, r.outcome, r.live_amount, r.live_currency,
       r.failure_code
FROM desktop_trial_readings r JOIN check_history h USING (check_id)
ORDER BY r.observed_at;
```
