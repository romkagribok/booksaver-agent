---
version: reconciliation-153d432
environment: production
created: 2026-09-20T18:01:01Z
status: complete
---

# Deployment and verification history

The user explicitly authorized the scoped AI-DLC implementation, verification, merge and deployment.
Bolt077/US192–194/Unit012 completed construction. Build → Development → Staging verification passed;
fe8ba21 was not promoted and is superseded by reviewed candidate 153d432. The replacement image
passed Development/Staging and current-head review, then confirmed merge and production verification.
Evidence below was reported by approximately 2026-09-20T18:00Z; exact event times are not inferred.

## Build and Development

Source `fe8ba21d9babbf06abecf98554c8d376f81e1b58` (runtime identical to `9e523d8`) produced
`booksaver-agent:reconciliation-fe8ba21`, immutable `sha256:173c7140519cf00e37d0d0cab0cf8c881dd9e4d7c68afa8c8f3736be2c34e335`.
The unchanged-dependency qualified base is `sha256:9ac7a7caa7f204354d5a58a82f6c63bdbfa33a51fc6320fc9a370cbb7cdc3f3a`. Installed-source comparison covered 123 modules;
eight pins, `pip check` and CLI passed. Network-disabled isolated Development verified SQLite/FKs,
Chromium and clean SIGTERM in **2.93 seconds**.

## Initial Staging admission halted

The first attempt stopped at the read-only-mount assertion **before account read or refresh**:
a CLI volume override had mounted production data read-write. The Compose volume was corrected to
explicit `read_only: true`. This failed admission is not a successful staging run and did not
establish a need to weaken the probe's production-data protection.

## Corrected exact-image Staging passed

The normal coordinator ran the affected caller on cloned state with notifications disabled, no
source overlay and no PYTHONPATH. The original production mount was asserted read-only.

- **39 checks passed, zero failed**; report **COMPLETE**, **4 discovered**, **2 eligible**.
- Old EUR104 reservation: **ABSENT**, ineligible, monitoring projection archived.
- Distinct EUR94 replacement: **UPCOMING**, eligible, monitoring projection active.
- **658 other-caller rows unchanged**; integrity/FK checks clean, with zero violations.
- Original production database digest unchanged. These are cloned-state results, not production
  reconciliation or native Telegram acceptance.

Protected logs: `/opt/booksaver-releases/reconciliation-20260920/build.log`, `dev.log`, `stage-2.log`.

## Review corrections supersede the staged image

Require exactly rowsPerPage10 rather than 1..25. Limit the bounded page collector to Trip records
actually referenced by the selected Active query; 30/150 unreferenced historical records must not
prevent valid scope qualification. Both issues are fixed with 69 parser / 170 total targeted tests.
The new full suite passed **2,818 tests**, 52 existing warnings, 52.42 seconds; Ruff/mypy123 clean.
At that point new exact installed-image Development/Staging remained pending. The fe8ba21 passes
remain historical candidate evidence; replacement qualification and promotion are recorded below.

## Replacement candidate 153d432 — qualified

Source `153d4320dd553e2d2c58d5231949697991009212`, tag `booksaver-agent:reconciliation-153d432`, immutable
`sha256:cddc642f8a3e6b1babaa070000c530027362de2933ab47575008fc7d5141155b`, built **2026-09-20T18:05:08.641935651Z**, size **701,874,085 bytes**.
All 123 installed modules match; eight pins/`pip check`/CLI passed. Development passed in **2.72 seconds**.

Exact installed-image Staging passed **39 checks**, zero failures, with **COMPLETE/4 discovered/2 eligible**.
Old reservation is absent/ineligible/archived; the separate EUR94 replacement is upcoming/active/eligible.
All **658 other-caller rows** remained unchanged, integrity/FKs had zero violations, and the read-only
production source database digest was unchanged. Notifications disabled, no source overlay/PYTHONPATH.

Current-head Bugbot **SUCCESS** took **3m29s**; the 153d432 merge gate passed with two resolved
review threads and zero unresolved. The first merge API attempts returned 504/405; that response
was not accepted as merge evidence. Confirmed completion is recorded below.

## Production promoted and independently verified

PR53 is confirmed **MERGED/CLOSED** at **2026-09-20T18:12:16Z**, merge revision
`ef51bc8a5b4367d55e59af4644d1d3178db7d957`. The merge API stalled; a normal non-force Git merge/push succeeded and GitHub registered
the PR as merged. The full merge tree was verified identical to reviewed source 153d432.

The exact qualified image `sha256:cddc642f8a3e6b1babaa070000c530027362de2933ab47575008fc7d5141155b` was promoted. The daemon started at
**2026-09-20T18:14:31.784745376Z**; independent verification completed at **2026-09-20T18:15:28Z**.

The normal production caller refresh passed **38 assertions**, **0 failures**, with **COMPLETE**,
**4 discovered**, **2 eligible**. Old EUR104 is **ABSENT/ineligible/archived**, with its identity and
total preserved; the separate EUR94 replacement is **UPCOMING/eligible/active**. All **658 other-caller
rows** were unchanged. SQLite integrity/FKs passed. No notifications were sent.

Service is running/healthy, **0 restarts**, **OOM false**, heartbeat **10 seconds old** at verification,
and internal/public health both HTTP **200**. Only Caddy publishes **80/443**; Caddy's container ID
is unchanged. Startup logs are clean. No leftover probes or detected orphan browser/display processes.

Backup: `/opt/booksaver-backups/reconciliation-153d432-20260920`, directory **0700**, archive/config/
env **0600**; tar validated. Archive SHA256:
`52c84002d4fc5ed060f0f8d3b4f0baf8eef9bccfb6a413ae5e90183770499684`.
Rollback tag `booksaver-agent:rollback-pre-reconciliation-153d432` was verified to retain
`sha256:9ac7a7caa7f204354d5a58a82f6c63bdbfa33a51fc6320fc9a370cbb7cdc3f3a`. No data restore was performed.
Protected evidence: `/opt/booksaver-releases/reconciliation-20260920/production-probe.log` and
`promotion-153d432.log` in the same directory.

Operations is complete using existing health/heartbeat/protected-log monitoring. This is normal
production inventory acceptance, distinct from prior cloned Staging. Native Telegram UI interaction
remains user-driven and is not claimed as tested. No new external alert service or SLO was introduced.
