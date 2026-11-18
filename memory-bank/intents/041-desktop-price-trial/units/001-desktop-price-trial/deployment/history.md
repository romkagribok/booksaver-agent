---
version: desktoptrial-34d89a8
environment: production
created: "2026-11-13T03:27:17Z"
status: complete
---

# Deployment and verification history

| Version | Merge | Image | Promoted | Release record |
|---|---|---|---|---|
| desktoptrial-34d89a8 | 34d89a8 | sha256:9a8ad272… | 2026-11-13T03:26:07Z | ../../../../operations/releases/34d89a8-desktop-price-trial.md |
| config-trialall (config only) | 34d89a8 | sha256:9a8ad272… (unchanged) | 2026-11-16T03:15:03Z | ../../../../operations/releases/config-trialall-desktop-trial-every-user.md |
| retiretrial-e6d1044 | e6d1044 | sha256:73fe9d8f… | 2026-11-18T13:12:35Z | ../../../../operations/releases/e6d1044-retire-desktop-price-trial.md |

Build → Development → Staging (live replay on the owner's session with the daemon paused, then the
release image's reader on fixtures) → Production with backup, config section and rollback tag →
read-back on user 4's 2026-11-13 12:36Z slot (four pairs, both verified pairs equal) → evaluation
scheduled for 2026-11-20T14:00Z (pending).

2026-11-16: the trial was widened from user 4 to every user (`user_ids = [1, 3, 4]`) by a config
change through the operations agent; candidate config validated in the container, backup taken,
container recreated and healthy. Read-back of user 1's 04:27Z slot: mobile and desktop both
USD 536, session untouched. The evaluation date is unchanged.

2026-11-18: the evaluation was done (53 pairs, 27 priced, all equal) and the owner retired the
trial. Build → Development → Staging (migration on a copy of the live database, offline, and the
previous image on the migrated copy) → Production with backup, config section removed and
rollback tag → read-back of the next scheduled slot.
