---
version: jevcmp-e6452e6
commit: e6452e63f4049ff85753d401f01f0fb6d2e0a331
created: "2026-09-27T16:46:07Z"
status: deployed-awaiting-key
---

# Paired Jev price comparison — released, awaiting the TypeSafe key

Intent 026 bolts 084–086: every admitted manual and scheduled price check also runs an independent
Jev-only method (TypeSafe `jev-1.13.0`) from the same session snapshot, and the booking owner gets
one Telegram report with both results. Only the existing method owns canonical effects (ADR-055).

## Artifact and verification

- Source `e6452e6` (PR #73); merge `f69cf12eefa2d4bc30ae027db084985853b5b878`, tree identical to source.
- Image `booksaver-agent:jevcmp-e6452e6` =
  `sha256:9b8497eb846d695e8d4718ebf194d3972a6eaf28200343dcffaaec4bab5d1861`, built on
  `connectwait-b2d272f`.
- Quality: 3,082 tests, one skip; Ruff and mypy (131 modules) clean; AI-DLC validators 0 errors,
  0 inconsistencies. An independent review pass found grounding and isolation issues; all fixed
  with regressions before release (bolt 086 test report).
- Bugbot: **waived**. Cursor reported its usage limit on head `e6452e6`
  (`scripts/bugbot_merge_gate.py 73` printed `waived`, 0 Cursor threads); owner-approved exception.
- Dev on the exact image: 131 installed modules match source, dependency pins matched, `pip check`
  clean, daemon/Chromium smoke, three supervisor cleanup cases, Jev modules import, CLI help.
- Staging: `jevcmp_stage_probe.py` on a `sqlite3.backup` production snapshot, `--network none`,
  browser work replaced by recorders: v18→v19 migration with integrity ok, 0 FK violations, 117
  history rows preserved; one baseline history row and one savings-pipeline call; both arms
  recorded; one two-row report captured (not delivered); daemon enables Jev only with config and
  key. (The probe's pre-migration version field reads after connect and therefore showed 19.)
  Snapshot copy deleted.
- Production: promoted 2026-09-27T16:46Z with backup `/opt/booksaver-backups/jevcmp-e6452e6-20260927`
  and rollback tag `booksaver-agent:rollback-pre-jevcmp-e6452e6`; healthy, zero restarts, OOM false,
  no published ports, Caddy unchanged, SQLite integrity/FKs ok, schema 19. Config now has
  `[jev_comparison] enabled = true, participants = "all"` (owner decision), daily cap USD 0.25.
  Without `BOOKSAVER_TYPESAFE_API_KEY` the daemon logs that checks stay baseline-only.

## Pending live acceptance (Gate B)

Owner adds `BOOKSAVER_TYPESAFE_API_KEY` to `/opt/booksaver-agent/.env` and recreates the container.
Then: first real TypeSafe calls, a native two-result report for a manual `/checknow`, a scheduled
report, and 5–7 days of observation (`booksaver comparison report`). Rollback: set
`enabled = false` (or remove the key) and recreate; history is kept.
Evidence: `/opt/booksaver-releases/jevcmp-20260927/` (build/dev/stage/promotion logs).
