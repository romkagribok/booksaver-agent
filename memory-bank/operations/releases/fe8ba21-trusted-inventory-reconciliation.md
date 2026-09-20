---
version: reconciliation-fe8ba21
commit: fe8ba21d9babbf06abecf98554c8d376f81e1b58
created: 2026-09-20T18:01:01Z
status: superseded
---

# Trusted inventory reconciliation — superseded, not promoted

The qualified current-list proof allows scoped retirement of absent active reservations while
preserving history and incomplete observations. It keeps exact cancellation/rebooking identities
separate and labels saved unverified records clearly. No remote booking is edited.

## Qualified artifact

- Source: `fe8ba21d9babbf06abecf98554c8d376f81e1b58`; runtime identical to `9e523d8`.
- Tag: `booksaver-agent:reconciliation-fe8ba21`.
- Image: `sha256:173c7140519cf00e37d0d0cab0cf8c881dd9e4d7c68afa8c8f3736be2c34e335`.
- Base: `sha256:9ac7a7caa7f204354d5a58a82f6c63bdbfa33a51fc6320fc9a370cbb7cdc3f3a`; dependency graph unchanged.
- Build verification: 123 installed modules byte-equal, eight dependency pins, `pip check` and CLI passed.
- Development: network disabled, isolated SQLite/FK/Chromium and clean SIGTERM; **2.93 seconds**.
- Quality: **2,803 tests**, 52 existing warnings, 51.16 seconds; Ruff/mypy123; 16 validator tests and no artifact/
  status errors. Subsequent synthetic-ID-only fixture edit: 227 focused tests passed, runtime unchanged.

## Staging evidence and corrected admission

The first admission stopped before account read because an overridden volume was read-write.
Explicit Compose `read_only: true` corrected the mount; the protection was not bypassed.
The corrected exact-installed-image normal-coordinator cloned replay passed **39 checks**, zero
failures, with **COMPLETE/4 discovered/2 eligible**. Old EUR104 is absent/ineligible/archived; the
separate EUR94 replacement is upcoming/eligible/active. All **658 other-caller rows** were unchanged,
integrity/FKs passed and the original production database digest was unchanged. Notifications were
disabled; no source overlay or PYTHONPATH was used.

Protected evidence: `/opt/booksaver-releases/reconciliation-20260920/build.log`, `dev.log`,
`stage-2.log`. Results were reported by approximately 2026-09-20T18:00Z (minute precision);
this record's creation time does not substitute for exact build/stage/promotion timestamps.

## Remaining release gates

Cursor Bugbot found two medium issues in fe8ba21. Source fixes now require exactly rowsPerPage10
and collect only Active-query-referenced Trip records instead of every cached historical Trip.
69 parser / 170 total targeted tests passed. The new full suite passed **2,818 tests**, 52 existing
warnings, 52.42 seconds; Ruff/mypy123 clean. Replacement-image qualification remains pending. The fe8ba21 image was not promoted and is superseded. A successful review/merge
gate for the corrected final head and new exact-image Development/Staging are required before merge. Production continues on prior qualified base image 9ac7a7c, healthy with
zero restarts/OOM false and Caddy untouched. Merge, backup/rollback confirmation, exact-image
promotion, normal production reconciliation and post-deployment checks are not yet complete.

The operator-only production probe is prepared locally for authorized post-promotion execution
with the daemon paused under a restart trap. It is not production acceptance evidence until run.
A repeat allows the old record to be already absent; it must preserve that history and the separate
eligible replacement. Assertions do not undo normal local reconciliation writes.

Complete this record after actual release results: source/merge/image/time, protected backup and
rollback, data/isolation assertions, restart/OOM state, logs, internal/public health, advancing
heartbeat, dependency/state integrity, published/internal ports and browser cleanup. Cloned Staging,
normal production inventory and native Telegram interaction remain distinct evidence. Monitoring
uses existing local health/heartbeat/protected logs; no new external monitoring service is introduced.
