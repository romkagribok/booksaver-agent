---
version: jevonly-a273c78
commit: a273c78d3388
created: "2026-10-12T23:15:40Z"
status: deployed-verified
recorded: "2026-10-12T23:16:49Z"
---

# Jev is the only price method in production (phase 2 of bolt 089)

The owner confirmed on 2026-10-12 that the other concurrent work was finished and asked for the
LLM price method to be removed from production if the Jev side looked good and Bugbot agreed.

## Evidence before the switch

24 paired checks on the phase 1 release, 2026-10-10T09:53Z to 2026-10-12T20:51Z:

| Booking | Pairs | LLM verified | Jev verified |
|---|---|---|---|
| Owner, USD | 8 | 7 | 8 |
| Invitee A, EUR | 8 | 1 | 8 |
| Invitee B, EUR, member-discounted room | 8 | 5 | 8 (was 0 of 27) |

Jev 24 of 24, LLM 13 of 24; identical price in all 13 pairs where both verified, including five on
the discounted room. Model cost USD 0.034 against USD 5.68. All 16 rates of the discounted hotel
were priced (`priced=16`); no run needed navigation or a reload.

## Defect found in the pre-check and fixed (PR #86)

Production had been redeployed at 2026-10-12T23:01Z with the meal gate (#84) and no check had run
on it. Running the gate's classifier on the affected hotel's real rate-card wording showed the Jev
path reporting `unknown` for breakfast rates, because the rate's name ("Flexible + Breakfast") was
passed as meal wording beside "Very good breakfast included in the price". Invitee B's reservation
is booked with breakfast, so under Jev alone it would never have verified. The name line is now
left out (US-217 criterion added before the fix).

## Artifact and verification

- Source `a273c78` (PR #86); merge `c8208447d43f288a0bf04ebb89637f2ae0c3c3b5`, tree identical.
- Image `booksaver-agent:jevonly-a273c78` =
  `sha256:e347951a7c156cd9e06f56f82b176ab1e69ab39bcfb7a80d8dea49e51a84937f`, built on
  `mealgate-507aa5b`.
- Quality: 3,289 tests, one skip; Ruff and mypy (133 modules) clean; AI-DLC validators 0 errors.
- Bugbot: **passed** on head `a273c78` (`scripts/bugbot_merge_gate.py 86` printed `passed`).
- Dev on the exact image: 133 installed modules match source, pins matched, `pip check`, daemon and
  Chromium smoke, three supervisor cleanup cases. No stage probe: no schema or coordinator change;
  the Jev-only configuration path was probed on a production snapshot in phase 1.
- Config: `config.toml.jevonly` (adds `price_executor = "jev"`, sets `[jev_comparison] enabled =
  false`; nothing else) was loaded by the exact image with no network before production was
  touched.
- Production: image and config promoted together 2026-10-12T23:15:40Z with backup
  `/opt/booksaver-backups/jevonly-a273c78-20261012` and rollback tag
  `booksaver-agent:rollback-pre-jevonly-a273c78`; healthy, zero restarts, no published ports,
  Caddy unchanged, SQLite integrity and foreign keys ok, schema 21, public health 200, no error
  lines. From inside the container: effective config `jev` / `consented_users` / paired off; the
  daemon wiring builds `JevPrimaryPriceExecutor`; startup log states Jev is the configured price
  method.

## Kill switch (US-215)

Turning paired mode off left 0 pending comparison arms, kept all 106 comparisons and 254 history
rows, and the paired candidate factory is absent, so no new Jev arm can start.

## Not yet observed

No price check had run in Jev-only mode when this was written (`jev_price_runs` empty). First
scheduled checks: owner 2026-10-13T02:03Z, invitees 02:22Z and 03:12Z. Unconfirmed until then:
the first canonical Jev result in production, and that invitee B's breakfast reservation selects a
breakfast rate under the meal gate (the fix was checked against that hotel's signed-out wording,
not a signed-in run). A failed scheduled check is silent, so this needs looking at:
`booksaver comparison report --days 1` and `check_history` for that booking.

## Observed (2026-10-13T13:54:35Z)

Six scheduled checks ran in Jev-only mode by 2026-10-13T10:52Z, two per active booking: all
canonical successes with `jev_price_runs` records. Invitee B's breakfast reservation excluded the
room-only rate and selected the breakfast rate on both of its checks. Container healthy, zero
restarts. The error-page reload (US-219) has still not been observed.

## Rollback

Restore `/opt/booksaver-backups/jevonly-a273c78-20261012/config.toml` (or remove the
`price_executor` line and set `enabled = true`) and recreate the container. The LLM adapters are
unchanged in the image. Decision review: GitHub issue #79.
Evidence: `/opt/booksaver-releases/jevonly-20261012/`.
