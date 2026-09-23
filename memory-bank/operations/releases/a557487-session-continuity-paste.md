---
version: continuity-a557487
commit: a557487c0976725a651a1cf3f858a46b18f36a33
created: "2026-09-22T01:42:44Z"
status: complete
---

# Session continuity and remote login paste — released and verified

Saved Booking.com logins are now renewed by quiet daily server-verified maintenance instead of
expiring at an incidental cookie deadline, with durable 15m/1h/6h/24h backoff, guarded recovery of
legacy locally-expired bundles, once-per-revision reconnect notices and a 48-hour "could not verify"
notice. Remote `/connect` login bridges explicit Cmd/Ctrl+V and a masked native paste field into the
selected field over the existing RFB keyboard channel; printable ASCII only, unsupported characters
rejected before insertion, no automatic submission, no clipboard retention. Full Unicode paste is a
measured packaged-stack limitation, not a passed test.

## Artifact and verification

- Source `a557487c0976725a651a1cf3f858a46b18f36a33` (PR #55); merge `8956f4d5a01eb025c38b94b0059c282f49e325bc`
  at 2026-09-22T01:40:43Z.
- Image `booksaver-agent:continuity-a557487` = `sha256:cb35711dc21eadba038f4f6fbcb82ef4b79bb4fffd76ce5d27389e93212c2700`,
  built 2026-09-22T00:09:38Z from the unchanged-dependency base `sha256:cddc642f…`; installed source
  fingerprint equals the Git tree; 125 modules and eight pins matched; `pip check` clean.
- Quality: 2,952 tests, one Linux-only skip, Ruff/mypy125, AI-DLC validator clean. Pre-release review
  found and fixed two reconnect-notice defects (Bolt 078 test report). Bugbot passed on the final head.
- Dev on the exact image: smoke, three Linux supervisor cleanup cases, 27 packaged paste checks.
- Staging: the identical verification code passed a 32-check read-only production-clone replay on
  candidate 53d021c on 2026-09-20; the final-image replay on 2026-09-22 could not obtain live proof
  because Booking.com's edge returned the empty-202 pending tuple for the VPS IP (fail-closed
  retry-later). The user accepted release on the earlier replay plus Dev evidence.
- Production: promoted 2026-09-22T01:41Z with verified backup
  `/opt/booksaver-backups/continuity-a557487-20260922` and rollback tag
  `booksaver-agent:rollback-pre-continuity-a557487`; healthy, zero restarts, OOM false, clean startup,
  only Caddy 80/443 published, no orphan browser processes, schema 18 quick_check ok.

Native Telegram paste acceptance and the first production renewal remain user-observed. Evidence:
`/opt/booksaver-releases/continuity-20260920/` (build/dev/stage/promotion logs).

## Hotfix paste-7995864 (2026-09-22)

Mobile feedback showed six-box verification codes received only one pasted character. PR #57 paces
keystrokes at 50 ms and re-checks ownership after each send. Image
`sha256:81bceb3e7d61749414f3f2d10119162714f01d3c42e7536f2bdd6afdfb5a50e8` (built on
`continuity-a557487`) passed installed-source, smoke, supervisor cleanup, 27 paste checks and the
new six-box probe, merged as `2d57401` and was promoted at 2026-09-22T02:37Z with backup
`/opt/booksaver-backups/paste-7995864-20260922` and rollback tag `rollback-pre-paste-7995864`.
Production healthy afterwards. Superseded VPS images were pruned with the user's approval (disk
96% → 24%); the current and rollback images and all backups were retained.

## Release seamless-f2bb781 (2026-09-23)

Seamless mobile paste (US-200, Bolt 080, ADR-052): layered explicit clipboard sources behind one
tap, immediate paced delivery of bulk arrivals without Insert, one-time-code hints, and no
placeholder backspaces on replacement autofill. Image
`sha256:c57ca9803e3b5a754ec6f6ae1a8f41636ffd6fa6990852ece5f66b7af9762987` merged as `4986db1`, promoted
2026-09-23T00:45Z with backup `/opt/booksaver-backups/seamless-f2bb781-20260923` and rollback tag
`rollback-pre-seamless-f2bb781`. Production healthy afterwards.

## Release resume-9fd6192 (2026-09-23)

Resumable `/connect` (US-201, Bolt 081, ADR-053): owner-reopenable launch link with one live
viewer, detach grace instead of cancel on leaving, activity-slid expiry under a 30-minute
ceiling, server-verified resume on reload. Bugbot found three defects before release (unbound
cookie resume, non-self-running grace, unearned stability credit); all fixed with regressions.
Image `sha256:369759b284c174e68faffef4653f13e8b807601c5bd514ffd52dc776e60a79ac` merged as `9239e72`,
promoted 2026-09-23T15:03Z with backup `/opt/booksaver-backups/resume-9fd6192-20260923` and
rollback tag `rollback-pre-resume-9fd6192`. Production healthy afterwards.
