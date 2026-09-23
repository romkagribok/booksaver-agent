---
version: fit-9a783f4
created: "2026-09-23T16:13:15Z"
status: complete
---

# Deployment history

## Dev (exact image)

`dev-9a783f4.log`: installed-source and dependency verification, `pip check`, isolated smoke
(2.70 s), three Linux supervisor cleanup cases, 31 packaged paste checks, the six-box probe on
five paths, and the new `window_fit_probe.py`, which reads the Xvfb framebuffer directly: mobile
480×726 and 480×960 windows are fullscreen with the page viewport equal to the framebuffer and a
full-bleed page covering 99.97–99.98% of pixels; desktop 1280×800 covers 99.79% (unchanged).
Session-verification staging was not repeated (no verification-path change).

## Production promotion

PR #63 merged **2026-09-23** as `2c87bf0bed5a43dc0802b013948aeacb20cca793` after current-head Bugbot
passed and the merge gate passed with one resolved thread. `promote-9a783f4.sh` backed up to
`/opt/booksaver-backups/fit-9a783f4-20260923` (0700/0600, archive SHA-256
`3ac2d8b72d746fc691d8a02d7ea1317a7ca502fd40f6bb2fac684d9fc171d92b`, verified), passed
pre-promotion SQLite checks, tagged `booksaver-agent:rollback-pre-fit-9a783f4`
(`sha256:369759b2…`), and recreated only BookSaver. Daemon started **2026-09-23T16:12:23Z**;
healthy at **16:12:34Z**. Post-promotion: running/healthy, 0 restarts, OOM false, heartbeat 6 s,
clean startup log, no host ports for 8080/5900/6080, no orphan browser processes, config
unchanged, SQLite quick_check ok, public health 200, disk 25%. Rollback: retag `latest` to the
rollback image and recreate; no data restore implied.
