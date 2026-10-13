---
version: mealgate-507aa5b
commit: 507aa5b
created: "2026-10-12T23:02:04Z"
status: deployed-verified
recorded: "2026-10-12T23:03:28Z"
---

# Meal plan gate — released and verified on the Jev path

Intent 027, bolt 091 (ADR-057 and its addendum), stories US-222 to US-225. Offer selection now
excludes an offer with fewer meals than a reservation that includes meals, and every savings
alert states both meal plans. This is the fix for the reported alert; release 1
(`d19f7b5-reservation-meal-plan.md`) only recorded the reservation's meal plan.

## Artifact and verification

- Source `507aa5b` (PR #84); merge `1ebf46d690d977c495c280798bbd851ac63a84dd` at
  2026-10-12T23:01:16Z, `src` identical to source.
- Image `booksaver-agent:mealgate-507aa5b` =
  `sha256:da5dca77450c86ca657ec62ec9f8e3df1fb4d36e1b392ff529ecad5d3ebdcd9b`, built on
  `bookedtotal-baf9b29`.
- Quality: 3,288 tests, one skip; Ruff and mypy (133 modules) clean; AI-DLC validators 0 errors,
  0 status inconsistencies. Coverage not measured.
- Bugbot: **passed** on head `507aa5b` with no findings (`scripts/bugbot_merge_gate.py 84` printed
  `passed`).
- Dev on the exact image, `--network none`: 133 installed modules match source, pins matched,
  `pip check`, daemon and Chromium smoke, three supervisor cleanup cases, CLI help.
- Staging: `mealgate_stage_probe.py` on a `sqlite3.backup` production snapshot, `--network none`,
  using the three real monitored bookings with synthetic offers. Reservation with breakfast: a
  cheaper room-only offer (`meal_plan_worse`) and a cheaper unread offer (`meal_plan_unknown`) were
  excluded and the breakfast offer was chosen; with only those two offers nothing was chosen. The
  two reservations without meals stayed unconstrained and chose the cheapest offer. Alerts stated
  both meal plans. Schema 21 before and after, integrity ok, zero foreign-key violations, history
  rows preserved. `STAGE PASS`. Snapshot deleted.
- Production: promoted 2026-10-12T23:02:04Z with backup `/opt/booksaver-backups/mealgate-507aa5b-20261012` and
  rollback tag `booksaver-agent:rollback-pre-mealgate-507aa5b`; healthy, zero restarts, OOM false,
  no published ports, Caddy unchanged, SQLite integrity and foreign keys ok, schema 21, public
  health 200. No traceback in the first scheduler passes: the release 1 startup defect did not
  recur (no migration ran, and `_migrate_v21` now tolerates a concurrent start). Configuration
  unchanged: `browser_use` price method with the paired Jev comparison on.

## Not verified at release

- No real Booking.com rate table was available, so US-222's criterion "matches saved real
  property pages" is open. The offer reader was tested on synthetic wording only.
- Jev's meal line is assumed to sit inside the rate row.
- On the Browser Use and legacy extraction paths the wording is model-copied (ADR-057 addendum).
- An uncertain reading excludes the offer, so the expected failure is a missed saving for a
  reservation with meals, not a false alert.

## Baseline for monitoring

The reservation that prompted this intent (breakfast included, paid 101.20 EUR) received five
alerts at 86 to 87 EUR between release 1 and this release. Expected from now on: no alert at a
room-only price; either a conclusive no-equivalent-offer result carrying `meal_plan_worse` or
`meal_plan_unknown`, or a saving on a rate that includes breakfast.

## Operations checkpoints

The owner approved merge and redeploy on 2026-10-12T22:56:19Z ("sounds good, merge, redeploy and
monitor dads booking for the next 24 hours to make sure it runs as expoected"). Build and staging
ran under that approval. Monitoring is the 24-hour read-back below; no separate monitoring
system was added.

## Read-back (2026-10-13T13:51:32Z)

Both scheduled checks of the reservation with breakfast since the release (03:16Z and 10:52Z on
2026-10-13) excluded the room-only rate for the booked room as `meal_plan_worse` and selected the
breakfast rate at 114 and 124 EUR, above the 101.20 EUR paid, so no alert was sent and no
opportunity was created. The two reservations without meals were unconstrained. 26 accepted
rates on three properties were classified `breakfast` or `none`, none `unknown`.

**This release had a defect on the Jev path**: the rate's name was passed as meal wording, so
breakfast rates read `unknown` and were excluded. The bolt 089 session found it against real
wording and fixed it in PR #86. Production moved to image `jevonly-a273c78` (that fix, Jev as
the only price method) at 2026-10-12T23:15Z, before any check ran on this image, so the evidence
above is for the fixed Jev path only. The Browser Use and legacy paths
have not run with the gate, and no alert with the new wording has been sent. The owner closed
the intent after about 15 of the 24 hours of monitoring. Details: bolt 091 test report.

## Pending (at release; superseded by the read-back above)

1. Read back that reservation's scheduled checks (03:12Z, 10:49Z and 17:08Z on 2026-10-13) and
   the per-candidate meal plans in their diagnostics; final review at 24 hours.
2. Complete bolt 091 with `bolt-complete.cjs` after the owner confirms.

Rollback: `docker tag booksaver-agent:rollback-pre-mealgate-507aa5b booksaver-agent:latest` and
recreate. No schema change, so the previous image runs unchanged. Evidence:
`/opt/booksaver-releases/mealgate-20261012/` (build, dev, stage and promotion logs).
