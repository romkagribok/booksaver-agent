---
stage: test
bolt: 088-price-comparison-qualification
created: "2026-10-10T01:49:30Z"
status: in-progress
---

# Release qualification and activation — evidence

## Gate A, release `jevcmp-e6452e6` (2026-09-27)

Full suite 3,082 passed; Ruff and mypy clean; exact-image dev checks; stage probe on a production
snapshot (v18 to v19 migration, integrity ok, zero foreign-key violations, baseline-only canonical
effects, both arms recorded, report captured not sent). Record:
`operations/releases/e6452e6-jev-price-comparison.md`.

## Gate B, live

- 2026-10-01: owner confirmed a native two-row report for a manual check.
- 2026-10-01 to 2026-10-10: 81 scheduled pairs for the owner and one invitee, all delivered; stored
  costs and results match the reports sampled.
- Promotions of follow-up images on 2026-10-01 and 2026-10-04 each passed health, integrity and
  port checks (`operations/releases/18f367e-*`, `ac72f12-*`).

## Criterion disposition

| Story | Criterion | Disposition |
|---|---|---|
| US-214 | Adversarial browser and ambiguous-offer fixtures | Partly: unit-level guard, grounding and injection-style cases; **dedicated adversarial browser fixture suite descoped** |
| US-214 | Baseline-only regression | Met: disabled mode unchanged, confirmed by independent review and tests |
| US-214 | Cloned state on the exact image: migration, cleanup, isolation | Met for migration, integrity, isolation and cleanup; **restart-negative cases on the image descoped** |
| US-214 | Gates pass and current-head Bugbot requirement met | Gates met. **Bugbot did not run on any of PRs #73 to #76**: Cursor reported its usage limit each time and the owner's standing waiver was applied |
| US-214 | Native Telegram for owner and invitee, manual and scheduled | Met for owner manual and scheduled and invitee scheduled; an invitee manual check was not observed |
| US-215 | Baseline works without a key; activation needs key and limits | Met. **Disclosure requirement descoped** by owner choice |
| US-215 | Deploy with backups, Caddy preserved, full verification | Met on three promotions |
| US-215 | Every admitted check generates both records and results | Met: 82 of 82 |
| US-215 | Kill switch stops new Jev arms, keeps history, resumes single-method checks | **Open**: to be exercised when paired mode is turned off in phase 2 of bolt 089 |
| US-215 | Decision package after 5 to 7 days; owner chooses | Met: bolt 087 report; owner chose adoption on 2026-10-06 |

This bolt stays in progress until the kill-switch criterion has production evidence.

## 2026-10-10T03:29:57Z — PR #78

Cursor Bugbot ran on PR #78 and passed with no findings, the first automated review of this
intent's code. The kill-switch criterion remains open until phase 2 of bolt 089.
