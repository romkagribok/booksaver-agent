---
intent: 041-desktop-price-trial
created: "2026-11-13T03:02:27Z"
completed: "2026-11-13T03:02:27Z"
status: complete
---

# Inception Log: desktop-price-trial

## Overview

**Intent**: One-week silent desktop price trial on the trial user's bookings (GitHub issue #7).
**Type**: brown-field (experiment)
**Created**: 2026-11-13

## Artifacts Created

| Artifact | Status | File |
|----------|--------|------|
| Requirements | ✅ | requirements.md |
| System Context | ✅ | system-context.md |
| Units | ✅ | units/001-desktop-price-trial/unit-brief.md |
| Stories | ✅ | units/001-desktop-price-trial/stories/*.md |
| Bolt Plan | ✅ | memory-bank/bolts/114-desktop-price-trial/bolt.md |

## Summary

| Metric | Count |
|--------|-------|
| Functional Requirements | 6 |
| Units | 1 |
| Stories | 3 |
| Bolts Planned | 2 |

## Decision Log

| Date | Decision | Rationale | Approved |
|------|----------|-----------|----------|
| 2026-11-12 | Trial on user 4's bookings, silent, one week; retire and close issue #7 if the readings do not matter | Most bookings, so most pairs | Owner: "We need to run a trial on my fathers booking without him necessary seeing ... we can retire this and close the issue" |
| 2026-11-13 | Readings run after all of a slot's normal checks, on their own time limit | A slot has one time allowance for every booking; a reading inside it could starve the user's real checks | Engineering |
| 2026-11-13 | Scheduled slots only, not `/checknow` | A reading would delay or follow a reply the user is waiting for; slots give about 15 pairs a day | Engineering |
| 2026-11-13 | Desktop reading never writes the session; qualify on the owner's session before enabling user 4 | Unknown whether Booking.com tolerates the session on a desktop profile | Engineering |
| 2026-11-13 | Config needs an end date; no report command | The trial must stop without anyone remembering it; the evaluation is one query | Engineering |
| 2026-11-13 | Human checkpoints skipped | Standing waiver, CLAUDE.local.md point 4 | Owner standing waiver |
| 2026-11-16 | Trial population widened from user 4 to every user (`user_ids = [1, 3, 4]`); `ends_on` unchanged | 27 pairs in three days came from two hotels and all 15 priced pairs were equal; more hotels wanted before deciding | Owner: "let's expand the test to all bookings (without users knowing for now) and wait a few more days and then decide" |
| 2026-11-16 | Amendment made through the inception agent; clarifying questions and review checkpoints skipped | Standing waiver, CLAUDE.local.md point 4 | Owner standing waiver |
| 2026-11-18 | Retire the trial: FR-6, US-270, bolt 115; close issue #7 | 53 pairs, 27 priced, all equal; desktop never cheaper | Owner, 2026-11-17: "Retire tomorrow at 8am and close the issue" |
| 2026-11-18 | Retirement stays in intent 041, not a new intent | FR-5 already names a follow-up bolt that removes the trial | Engineering |
| 2026-11-18 | Schema 26 drops the table; `jev_price_runs` rows of the trial are kept | Production is at schema 25; the Jev rows are the spend ledger | Engineering |
| 2026-11-18 | Inception checkpoints skipped | Standing waiver, CLAUDE.local.md point 4 | Owner standing waiver |

## Scope Changes

| Date | Change | Reason | Impact |
|------|--------|--------|--------|
| 2026-11-13 | Issue #7's dual-channel selection, alerts, provenance and concurrency left out | The owner wants evidence first | Decided after the evaluation |
| 2026-11-18 | The rest of issue #7 (dual-channel checks) will not be built | The trial found no desktop price below mobile | Issue #7 is closed with the numbers after the removal is live |
| 2026-11-16 | Trial covers every user, not only user 4 | Thin sample; the owner asked for all bookings | Configuration only: no unit, story, bolt, code or schema change. Adds one booking today (user 1); desktop readings now load pages on every user's saved session |

## Ready for Construction

- [x] All requirements documented
- [x] System context defined
- [x] Units decomposed
- [x] Stories created for all units
- [x] Bolts planned
- [x] Human review: skipped under the standing waiver

## Next Steps

1. `/specsmd-construction-agent --unit="001-desktop-price-trial" --bolt-id="114-desktop-price-trial"`
