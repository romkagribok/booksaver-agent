---
version: config-trialall
commit: 34d89a8
created: "2026-11-16T03:15:03Z"
status: deployed-verified
recorded: "2026-11-16T05:00:28Z"
---

# Desktop price trial widened to every user (config only, intent 041, GitHub issue #7)

## Change

Production `/opt/booksaver-agent/config.toml` `[desktop_trial] user_ids` `[4]` -> `[1, 3, 4]`
(every user). `ends_on` stays `"2026-11-20"`. Image unchanged
(`booksaver-agent:desktoptrial-34d89a8`, `sha256:9a8ad272…`, still `latest`). No code or schema
change. Owner, 2026-11-16: "let's expand the test to all bookings (without users knowing for now)
and wait a few more days and then decide".

## Why

Interim read on 2026-11-15T22:52Z, three days in: 27 pairs for user 4, 15 where both sides
verified a price and all 15 equal (the price moved between 146 and 148 USD and desktop followed
it), 12 where both failed the same way, none one-sided. They came from two hotels only; user 4 has
three active bookings and one never yields a price on either side. The owner wants more hotels
before deciding and expects to retire the trial.

On 2026-11-16 user 1 has one active booking and user 3 none, so the change adds about three
pairs a day from one more hotel. It also means desktop readings now load pages on every user's
saved session; the safeguards are the ones already in the code (no session write, readings stop
at a sign-out or bot wall, half the Jev daily cap, `user_ids = []` turns it off).

## Is the desktop reading really desktop

Checked on 2026-11-16 because every priced pair was equal. One public hotel page was loaded in the
production container with the release's own browser host, once per profile, with no saved session
(four anonymous page loads in all):

| | Desktop trial profile | Mobile profile |
|---|---|---|
| User agent | Windows Chrome 151 | Pixel 7 Android Chrome 151 |
| Width, touch points | 1280, 0 | 412, 5 |
| `#hprt-table` / rate cards | present / 0 | absent / 2 |
| Rooms read, prices | 2: USD 148, USD 153 | 2: USD 148, USD 153 |

Each reading also passes the same sign-in probe as a normal check before it opens the hotel page.
In production the desktop runs send a different amount of page text from the mobile runs for the
same hotel (7,357 against about 7,940 input tokens), which they would not if both saw one page.
Not shown by this: the signed-in desktop page was seen directly only in staging on the owner's
session. Neither hotel shows a mobile-only price, so equal prices are what the site shows.

## Artifact and verification

- Environments: no build and no image, so the development and staging steps were the candidate
  file loaded with the release's `load_config` inside the production container before it was
  applied: `user_ids [1, 3, 4]`, `ends_on 2026-11-20`, active for users 1, 3 and 4 and not for an
  unknown user 2. Human checkpoints skipped under the standing waiver.
- No slot was running and no browser was open; the next slot was user 1's at 04:27:31Z.
- Backup `/opt/booksaver-agent/config.toml.pre-trialall-20261116T031503Z`; the diff is the one
  line. `docker compose up -d --force-recreate booksaver` at 03:15:03Z; started 03:15:27Z, healthy
  at 03:15:37Z, restart count 0, same image id.
- After the restart: the mounted config loads as active for users 1, 3 and 4; the eight planned
  slots of the day are still planned; startup log normal.
- Rollback: restore the backup (trial back to user 4 only) and recreate; or `user_ids = []`.

## Production read-back

Read on 2026-11-16T05:00:28Z, read-only, through the operations agent: user 1's first slot under
the widened trial (planned 04:27:31Z, ran 04:27:31Z to 04:30:01Z, completed).

| | Mobile check | Desktop reading |
|---|---|---|
| Time | 04:29:21Z | 04:30:01Z |
| Outcome, price | success, USD 536 | success, USD 536 |
| Jev run | observed, USD 0.00136, 26.4 s | observed, USD 0.00125, 40.2 s |
| Rooms, rates, priced | 5, 11, 11 | 5, 11, 11 |

- The slot wrote one `check_history` row, the mobile check; its session authentication is
  `validated` and the session revision is the one of user 1's three checks on 2026-11-15, so the
  reading did not write or disturb the saved session.
- `desktop_trial_readings`: user 1 one row, user 4 twenty-nine. No `auth_required` or `bot_wall`
  for any user since the change. Container healthy, restart count 0, started 03:15:27Z.
- User 3 has no active booking, so its slots take no reading; user 4's next slot is 07:15:45Z and
  runs as it has since 2026-11-13.

## Evaluation (FR-5)

Unchanged: 2026-11-20T14:00Z, now over every user's pairs. The owner decides keep or retire.
