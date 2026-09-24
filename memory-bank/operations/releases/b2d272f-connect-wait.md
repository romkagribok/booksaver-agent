---
version: connectwait-b2d272f
commit: b2d272f692a57f967ed2303f3fee3318fd16ca47
created: "2026-09-24T00:08:30Z"
status: complete
---

# /bookings and /checknow wait for the post-connect sync — released

User feedback: right after `/connect`, `/bookings` answered "BookSaver is busy" because the
post-connect inventory sync held the single browser gate. Now a same-user `/bookings` joins the
in-flight sync and receives its result; `/checknow` defers its picker or selected check until the
sync settles; and a price check reuses a complete inventory sync from the last 60 s instead of
re-synchronizing. Other users still receive BUSY; failed, partial or raising syncs are never reused.

## Artifact and verification

- Source `b2d272f` (PR #71); merge `ae3f15d8ffb95f7ed3fb9463dcf5ed9c17f0e446`, tree identical to source.
- Image `booksaver-agent:connectwait-b2d272f` =
  `sha256:021c06ed8bbeabab836f57e71b7ddf3f6e42da860dc9e7aaf5c3c05d1e4eb627`, built on
  `propertyref-3ac31c1`.
- Quality: 3,031 tests, one skip, Ruff and mypy (125 modules) clean. An independent review pass found
  a stale cache entry after a raising sync and a lost-waiter window on worker start failure; both
  fixed with a regression before release.
- Bugbot: **waived**. Cursor reported its usage limit on head `b2d272f`
  (`scripts/bugbot_merge_gate.py 71` printed `waived`); owner-approved exception per AGENTS.md.
- Dev on the exact image: installed source and pins matched, `pip check` clean, smoke, three
  supervisor cleanup cases.
- Staging: `connectwait_stage_probe.py` on a `sqlite3.backup` snapshot of production with
  `--network none` (sync and price steps replaced by recorders): connect accepted, same-user
  `/bookings` joined, `/checknow` deferred, another user BUSY, nothing delivered before release,
  both callbacks got the same saved reservations, and the following price check reused the
  connect sync (one sync run). Snapshot copy deleted afterwards.
- Production: promoted 2026-09-24T00:08Z with backup
  `/opt/booksaver-backups/connectwait-b2d272f-20260923` and rollback tag
  `booksaver-agent:rollback-pre-connectwait-b2d272f`; healthy, zero restarts, OOM false, no
  published ports, Caddy unchanged, SQLite integrity and foreign keys ok, Telegram gateway enabled.

Live Telegram acceptance (connect, then immediate `/bookings` and `/checknow`) is user-observed.
Evidence: `/opt/booksaver-releases/connectwait-20260923/` (build/dev/stage/promotion logs).
