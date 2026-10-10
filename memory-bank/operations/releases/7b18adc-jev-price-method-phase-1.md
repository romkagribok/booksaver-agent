---
version: jevprimary-7b18adc
commit: 7b18adc42068738abae69abe541f2fe5930315ad
created: "2026-10-10T02:42:22Z"
status: deployed-phase-1
recorded: "2026-10-10T03:29:57Z"
---

# Jev as the price method — phase 1 released (both methods still running)

Bolt 089 (ADR-056). The image can run Jev as the only price method, but production configuration
was deliberately left unchanged: `price_executor = browser_use` with the paired Jev comparison on.
The owner chose to confirm one booking under the new Jev rules before the switch.

## Artifact and verification

- Source `7b18adc` (PR #78); merge `91153247cefcb26e315e80a614e30c4962126c86`, tree identical.
- Image `booksaver-agent:jevprimary-7b18adc` =
  `sha256:ec6599c9c78d17993495e4fd780c91e2e19dd2f5b14d37471b6ba163aea5d1da`, built on
  `jevdiag-ac72f12`.
- Quality: 3,153 tests, one skip; Ruff and mypy (132 modules) clean; AI-DLC validators 0 errors,
  0 status inconsistencies. An independent review found two high-severity false-low-price paths in
  an earlier version of the grounding; fixed with regressions before the PR was opened.
- Bugbot: **passed** on head `7b18adc` (ran 7m41s, no findings;
  `scripts/bugbot_merge_gate.py 78` printed `passed`). First PR of intent 026 it has reviewed.
- Dev on the exact image: 132 installed modules match source, pins matched, `pip check`, daemon and
  Chromium smoke, three supervisor cleanup cases.
- Staging: `jevprimary_stage_probe.py` on a `sqlite3.backup` production snapshot, `--network none`,
  browser and provider replaced by recorders. v19 to v20 migration with integrity ok, zero
  foreign-key violations, 230 history rows and 82 comparisons preserved. Paired configuration:
  one baseline history row, one savings-pipeline call, both arms recorded, one two-row report
  captured. Jev-only configuration through the real monitor and primary executor: Jev's result
  canonical, one history row, one `jev_price_runs` record with diagnostic, session refreshed, no
  comparison. Jev with paired mode rejected at config load. `STAGE PASS`. Snapshot deleted.
- Production: promoted 2026-10-10T02:42:22Z with backup
  `/opt/booksaver-backups/jevprimary-7b18adc-20261010` and rollback tag
  `booksaver-agent:rollback-pre-jevprimary-7b18adc`; healthy, zero restarts, no published ports,
  Caddy unchanged, SQLite integrity and foreign keys ok, schema 20, public health 200, no error
  lines. Effective config confirmed from inside the container: `browser_use`, paired on,
  participants all, adapter `jev-price-v3`.

## Concurrent work

PR #77 (meal plan) had also claimed schema v20, bolt 089 and US-216. Its author session agreed to
rebase after this release and take v21 and the next numbers; the hand-off is recorded as comments
on #77. A third, uncommitted branch had chosen the same bolt, story and ADR numbers and will
renumber after #77.

## Pending (phase 2)

1. On the first scheduled checks after 02:42Z, confirm from `price_comparison_arms`:
   the member-discounted booking is verified by Jev or its diagnostic names the unpriced reason;
   the two bookings Jev verified before are still verified under the stricter rules.
2. Then set `price_executor = "jev"` and `[jev_comparison] enabled = false` in
   `/opt/booksaver-agent/config.toml` and recreate the container. This also exercises the paired
   mode kill switch (bolt 088).
3. Rollback: revert those two lines and recreate. Revert the config before any older image.

Decision review is tracked in GitHub issue #79.
Evidence: `/opt/booksaver-releases/jevprimary-20261010/` (build, dev, stage and promotion logs).
