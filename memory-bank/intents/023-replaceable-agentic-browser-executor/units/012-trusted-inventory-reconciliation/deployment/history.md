---
version: reconciliation-fe8ba21
environment: staging
created: 2026-09-20T18:01:01Z
status: in-progress
---

# Deployment and verification history

The user explicitly authorized the scoped AI-DLC implementation, verification, merge and deployment.
Bolt077/US192–194/Unit012 completed construction. Build → Development → Staging verification passed;
fe8ba21 was not promoted and is now superseded by review corrections. Replacement-image build,
Development/Staging and current-head review are pending before production promotion.
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
New exact installed-image Development/Staging remains pending. Preserve the
fe8ba21 passes as historical candidate evidence; the corrected source is not yet staged or promoted.

## Production pending

Production still runs prior image `sha256:9ac7a7caa7f204354d5a58a82f6c63bdbfa33a51fc6320fc9a370cbb7cdc3f3a`, healthy with zero restarts and OOM false; Caddy was
untouched. Bugbot identified two medium issues in `fe8ba21`; both source fixes require a new
current-head review and replacement image. No merge or promotion is claimed.

After the successful review gate, record merge SHA, verified restricted backup/rollback, exact
qualified image promotion, and the authorized notification-free normal production refresh. Verify
COMPLETE with 4 discovered / 2 eligible, old retirement, separate replacement, other-caller isolation and database checks,
then restore/verify daemon process/logs/health/heartbeat/ports/browser cleanup. Retain the existing
monitoring mechanisms; no new external alert destination or SLO is introduced by this release.
