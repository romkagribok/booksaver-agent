---
version: desktoptrial-34d89a8
commit: 34d89a8
created: "2026-11-13T03:26:07Z"
status: deployed-verified
recorded: "2026-11-13T13:22:40Z"
---

# One-week silent desktop price trial (intent 041, GitHub issue #7)

## Change

Bolt 114 (US-268, US-269).
- **Desktop reading:** after a scheduled slot's normal checks, each checked booking of a trial user
  is read once more in a desktop Chromium profile and stored in `desktop_trial_readings` under
  the mobile check's id. The reading uses the same Jev method, validators and offer selection.
- **Silent:** a reading writes no check history, trace, savings or alert, is not a check, and never
  writes the saved session. Its Jev spend is recorded as `jev-price-desktop-trial` and it stops
  at half the user's daily cap. A sign-out or bot wall on any check ends the slot's readings.
- **Config:** `[desktop_trial] user_ids = [4]`, `ends_on = "2026-11-20"` (readings through
  2026-11-19 UTC). Owner, 2026-11-12: "We need to run a trial on my fathers booking without him
  necessary seeing ... If over the course of the week, the readings don't matter much, we can
  retire this and close the issue".
- **Schema 25:** one additive table. An older image ignores it and the config section.

## Artifact and verification

- PR #123, head `b6837fa`, merge `34d89a8e32a1`. Codex rounds:
  - `bf53372`: P1, a desktop rate's capacity was compared with the adults only; P2, a bot wall
    on a later mobile check did not prevent readings for earlier bookings. Both fixed in
    `b6837fa` with a test each; threads resolved.
  - `b6837fa`: no major issues.
  - `scripts/codex_merge_gate.py 123` passed (exit 0) before the merge.
- Image `booksaver-agent:desktoptrial-34d89a8` =
  `sha256:9a8ad2726df08f86dfeed4ace277eb18e130f516670e6d4055e3902a1d5a7fab`. Built from the
  merge's `git archive` on `legible-8fab90f`; 118 modules.
- Quality: 2,655 passed, 1 skipped. Ruff and mypy clean. AI-DLC validation found 0 inconsistencies.
- Development: `pip check` clean and the production config valid in the image, trial off without
  the new section.
- Staging:
  - Candidate `bf53372` (kit `desktoptrial-20261113`), live replay on cloned data with the
    daemon paused 03:17:15Z to 03:19:31Z and restored healthy, owner's session and booking only
    (owner alerts were disabled; no other user's session was used):
    - Mobile check: USD 536, 41 s.
    - Desktop reading through the trial loop: signed-in desktop room table read as 5 rooms and
      11 rates, all 11 priced and all-in; USD 536; 40 s; 19 Jev calls, USD 0.0012; stored as one
      reading; session revision unchanged; no history row.
    - Mobile check again afterwards: USD 536, 26 s. The session was still valid.
  - Release source (merge; differs from the candidate in the two review fixes): the image's
    reader passed the four room-table fixtures in its own Chromium with no network.
- Promotion: backup `/opt/booksaver-backups/desktoptrial-34d89a8-20261113`. Healthy, SQLite
  integrity, schema 25, `desktop_trial_readings` empty, public health passed, Caddy unchanged at
  2026-11-13T03:26:07Z. In the running container the trial executor is built and the trial is
  active for user 4 and not for user 1. Rollback: `user_ids = []` turns the trial off;
  `booksaver-agent:rollback-pre-desktoptrial-34d89a8` with the backed-up config restores the
  previous release.

## Production read-back

Read 2026-11-13T13:20Z. User 4's slot planned for 12:36:02Z completed. It checked his four active
bookings on mobile (12:38:43Z to 12:40:17Z), then took four desktop readings (12:40:17Z to
12:42:44Z, about two and a half minutes), one per booking, each joined to its mobile check:

| Booking | Mobile | Desktop |
|---|---|---|
| Ayres Hotel Vista Carlsbad | USD 146 | USD 146 |
| AIRINN Vilnius Airport Hotel | EUR 157 | EUR 157 |
| Park Plaza Lodge | no price verified (`extraction_failed`) | no price verified (`extraction_failed`) |
| Residence Kalipè | no availability (`no_equivalent_offer`) | no availability (`no_equivalent_offer`) |

- **Both verified pairs match exactly; desktop was not cheaper.** The two failures have the same
  cause on both sides: the run diagnostics agree line for line (same room and rate counts, no room
  named for Park Plaza, unavailable for Kalipè). Both bookings were already failing on mobile
  before the trial.
- **Nothing else was written.** No check history row carries a desktop source, no savings
  opportunity or alert since the promotion, and no reading shares a check id with one. His session
  file was last written at 12:40, by the last mobile check, not by the readings.
- **His checks look as before.** No `auth_required` or `bot_wall` for any user since the
  promotion; his outcome mix for the slot (2 verified, 1 `extraction_failed`, 1
  `no_equivalent_offer`) is the mix of the previous two days.
- **Cost and health.** Four `jev-price-desktop-trial` runs, USD 0.0051 in total, 27 to 41 seconds
  each. Container healthy, no restarts, schema 25. The log has no trial warning; Telegram polling
  had its usual transient connection resets, which retried.

## Evaluation (FR-5)

Read from production on 2026-11-18T13:00:20Z, before the removal (read-only, through the
operations agent). The trial covered user 4 from 2026-11-13 and every user from 2026-11-16.

| | User 4 | User 1 | Total |
|---|---|---|---|
| Pairs taken | 46 | 7 | 53 |
| Both sides verified a price | 24 | 3 | 27 |
| Of those, equal price | 24 | 3 | 27 |
| Desktop cheaper by 5 or more | 0 | 0 | 0 |
| Both failed | 21 | 4 | 25 |
| One-sided | 1 | 0 | 1 |

- **Hotels.** Five in all; three gave priced pairs (15, 9 and 3 pairs). No currency differed.
- **Both failed.** 10 `extraction_failed` on both sides, 14 `no_equivalent_offer` on both, 1 mixed.
  They are two properties that never yielded a price on either side and, from 2026-11-17, user 1's
  hotel, which was sold out for the booked dates (seen on the public page in both profiles).
- **One-sided.** 2026-11-16T11:19Z, the day before check-in: mobile `no_equivalent_offer`,
  desktop a different room ("Business Double Room with Kitchenette") at EUR 167 against a booking
  at EUR 102. Checked by hand: not a saving. The slot before had the same room at EUR 167 on both
  sides and the slot after failed on both.
- **Cost and latency.** 53 desktop runs, USD 0.0494 in total, 35.1 s on average.
- **Safety.** No `auth_required` or `bot_wall` for any user since 2026-11-13T03:26Z. Mobile
  success rates did not change with the trial.
- **End.** The trial was removed on 2026-11-18T13:12:35Z, before its `ends_on`; no reading exists
  after that.

**Decision.** Owner, 2026-11-17 22:48 EST: "Retire tomorrow at 8am and close the issue". Desktop
never showed a price below mobile for the same room, so the dual-channel checks of issue #7 are
not built. Removed by bolt 115; release record `e6d1044-retire-desktop-price-trial.md`.
