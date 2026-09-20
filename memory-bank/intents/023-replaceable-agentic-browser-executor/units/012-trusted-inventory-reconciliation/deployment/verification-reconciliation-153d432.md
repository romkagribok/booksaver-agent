---
version: reconciliation-153d432
environment: production
verified: 2026-09-20T18:15:28Z
created: 2026-09-20T18:16:36Z
status: passed
---

# Production verification

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

