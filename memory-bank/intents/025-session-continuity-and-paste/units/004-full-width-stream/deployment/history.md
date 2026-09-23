---
version: nohelp-9491bcd
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

## Release touch-c8b2aa6 — no cursor on touch, tablet-sized framebuffers (US-203, Bolt 083)

PR #65 (head `c8b2aa6bd5c3b0be9014f9690148c0045143650f`): x11vnc runs with `-nocursor` for mobile
logins; the mobile framebuffer width follows the touch viewer's width within 480–1024. Bugbot
passed on the head; merge gate passed with zero threads. Full suite 2,990 passed, Ruff, mypy125.

Image `booksaver-agent:touch-c8b2aa6` = `sha256:e1e0965fe0de55efcf344e44e88a054032e926fa9834f1c7f8557c52a3e69f7f`,
built 2026-09-23T16:41:56Z on base `fit-9a783f4`; installed-source fingerprint equals the Git tree;
125 modules and eight pins matched; `pip check` clean. Dev (`dev-c8b2aa6.log`): smoke 2.66 s,
three supervisor cleanup cases, 31 paste checks, six-box probe on five paths, and the window-fit
probe with the new tablet case: 1000×1200 fullscreen with the viewport equal to the framebuffer
and a full-bleed page covering 99.99% of pixels, alongside the phone and desktop cases.

Merged **2026-09-23** as `9936499e3c6c4a0747568f202d5a4712ce39eb90`; `promote-c8b2aa6.sh` backed up to
`/opt/booksaver-backups/touch-c8b2aa6-20260923` (0700/0600, archive SHA-256
`16297845b3e03e739ff613fdf44a8db86e485499574d59d4f5b8bf391fe04791`, verified), passed
pre-promotion SQLite checks, tagged `booksaver-agent:rollback-pre-touch-c8b2aa6`
(`sha256:eacb75e9…`), and recreated only BookSaver. Daemon started **2026-09-23T16:44:02Z**;
healthy at **16:44:12Z**. Post-promotion: running/healthy, 0 restarts, OOM false, heartbeat 5 s,
clean log, no host ports for 8080/5900/6080, no orphan browser processes, config unchanged,
SQLite quick_check ok, public health 200, disk 25%.

## Release nohelp-9491bcd — help control removed

PR #67 (head `9491bcd6f60b26625343cebd15453828bb8082d8`): the "?" control and help paragraph are
removed; the status keeps a fixed two-line height so the measured viewer area stays stable; the
connected message is shortened. Bugbot passed; merge gate passed with zero threads. Full suite
2,990 passed, Ruff, mypy125.

Image `booksaver-agent:nohelp-9491bcd` = `sha256:8315daba34c3d1742abfde5115d0ac14f03d369fb228d6adbc61d70bfe0126c3`,
built 2026-09-23T19:48:09Z on base `touch-c8b2aa6`; installed-source fingerprint equals the Git
tree; 125 modules and eight pins matched; `pip check` clean. Dev (`dev-9491bcd.log`): all seven
probes passed (smoke, three supervisor cases, 31 paste checks, six-box probe, window-fit probe
with phone, tablet and desktop cases).

Merged **2026-09-23** as `5e1d018affdd74ca4fd9540bc7fd07b29b8ba5a7`; `promote-9491bcd.sh` backed up
to `/opt/booksaver-backups/nohelp-9491bcd-20260923` (archive SHA-256
`58cdbd5eb3ee9753a6212e469d34bc1a4c4b3b0a0a47e4d3d42f1fb4db92caca`, verified), tagged
`booksaver-agent:rollback-pre-nohelp-9491bcd` (`sha256:e1e0965f…`) and recreated only BookSaver.
Daemon started **2026-09-23T19:50:32Z**; healthy at **19:50:42Z**. Post-promotion: running/healthy,
0 restarts, OOM false, heartbeat 6 s, clean log, no private host ports, no orphan browser
processes, config unchanged, SQLite quick_check ok, public health 200, disk 25%.
