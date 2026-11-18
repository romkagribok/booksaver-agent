---
version: retiretrial-e6d1044
environment: production
verified: "2026-11-18T13:20:24Z"
created: "2026-11-18T13:20:24Z"
status: passed
---

# Production verification

- Promotion at 2026-11-18T13:12:35Z: healthy, no restarts, schema 26, `desktop_trial_readings`
  gone, internal and public health passed, Caddy unchanged, no host port published, config
  without the `[desktop_trial]` section valid in the image.
- In the running container: no `booksaver.daemon.desktop_trial` module; the 53 trial rows in
  `jev_price_runs` kept.
- Read-back of the first slot on the new image (user 1, 13:17:47Z to 13:19:51Z): reservation sync
  and mobile price check ran; the page showed no availability (the hotel is sold out for the
  dates); no desktop run; no error in the log. A check ending in a price was not yet seen.
