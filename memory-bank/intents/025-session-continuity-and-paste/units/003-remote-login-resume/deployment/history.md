---
version: resume-9fd6192
created: "2026-09-23T15:04:32Z"
status: complete
---

# Deployment history

## Dev (exact image)

`dev-9fd6192.log`: installed-source and dependency verification, `pip check`, isolated
network-disabled smoke (2.76 s), three Linux supervisor cleanup cases, 31 packaged paste checks
and the six-box probe on five paths, all passed. Session-verification staging was not repeated:
no verification-path change, and the user asked not to probe Booking.com's edge.

## Production promotion

PR #61 merged **2026-09-23** as `9239e72e733005df25f1c6afa176d9621d5d8895` after current-head Bugbot
passed and the merge gate passed with three resolved threads. `promote-9fd6192.sh` backed up to
`/opt/booksaver-backups/resume-9fd6192-20260923` (0700/0600, archive SHA-256
`dff12b5f2bcc54124b6b7b824006c31ee0701d24016774ac63afd05f14329f7f`, verified), passed
pre-promotion SQLite checks, tagged `booksaver-agent:rollback-pre-resume-9fd6192`
(`sha256:c57ca980…`), and recreated only BookSaver. Daemon started **2026-09-23T15:03:29Z**;
healthy at **15:03:40Z**. Post-promotion: running/healthy, 0 restarts, OOM false, heartbeat 10 s,
clean startup log, no host ports for 8080/5900/6080, no orphan browser processes, config unchanged,
SQLite quick_check ok, public health 200, disk 25%. Rollback: retag `latest` to the rollback image
and recreate; no data restore implied.
