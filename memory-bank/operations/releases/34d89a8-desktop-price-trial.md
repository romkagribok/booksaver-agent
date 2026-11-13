---
version: desktoptrial-34d89a8
commit: 34d89a8
created: "2026-11-13T03:26:07Z"
status: deployed
recorded: "2026-11-13T03:27:17Z"
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

Pending: user 4's first slot after the promotion is planned for 2026-11-13T12:36:02Z. To record:
readings stored for that slot, his mobile results and session unaffected, no user-visible change.

## Evaluation (FR-5)

Pending: after 2026-11-20. Pairs taken, pairs where both sides verified a price, pairs where
desktop was cheaper by 5 or more in the booking currency, desktop failure reasons, and the owner's
decision to keep or retire.
