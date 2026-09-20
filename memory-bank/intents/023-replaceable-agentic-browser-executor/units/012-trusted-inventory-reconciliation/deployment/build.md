---
version: reconciliation-fe8ba21
commit: fe8ba21d9babbf06abecf98554c8d376f81e1b58
created: 2026-09-20T18:01:01Z
status: superseded
---

# Build: trusted inventory reconciliation — superseded candidate

- Tag: `booksaver-agent:reconciliation-fe8ba21`.
- Immutable image: `sha256:173c7140519cf00e37d0d0cab0cf8c881dd9e4d7c68afa8c8f3736be2c34e335`.
- Qualified base: `sha256:9ac7a7caa7f204354d5a58a82f6c63bdbfa33a51fc6320fc9a370cbb7cdc3f3a`.
- Source: `fe8ba21d9babbf06abecf98554c8d376f81e1b58`; runtime source is identical to `9e523d8`.
- Built on the VPS using the qualified base with unchanged dependencies. All **123 installed
  modules** matched source byte for byte; **eight dependency pins**, `pip check`, and CLI passed.
- Protected build log: `/opt/booksaver-releases/reconciliation-20260920/build.log`.

Evidence was reported by approximately **2026-09-20T18:00Z** (minute precision). The frontmatter
creation time is this document's creation, not an inferred build/deployment event timestamp.
The exact image build time and size were not supplied and are not invented here.

## Development verification

The exact installed image passed isolated SQLite/foreign-key checks, Chromium startup and clean
SIGTERM shutdown in **2.93 seconds**, with networking disabled. Log:
`/opt/booksaver-releases/reconciliation-20260920/dev.log`.

Construction gate: **2,803 tests**, **52 existing warnings**, **51.16 seconds**; Ruff/mypy123 clean.
The later fixture-only replacement of real confirmation IDs with synthetic values passed **227
focused tests** without runtime changes. AI-DLC: 16 validator tests, zero errors/inconsistencies.

Exact-image cloned Staging passed as recorded in history, but this image was **not promoted**.
Bugbot found two medium issues: the parser accepted rowsPerPage 1..25 instead of exactly 10, and
collecting all cached Trip records could reject valid Active scope because of unrelated history.
Both source fixes require a replacement image and fresh current-head review/Development/Staging.
This artifact's earlier passes do not qualify the corrected source or authorize its promotion.

The corrected source passed **2,818 tests**, 52 existing warnings, 52.42 seconds, with clean
Ruff/mypy123. A new image is still required; these results do not change this artifact's superseded status.
