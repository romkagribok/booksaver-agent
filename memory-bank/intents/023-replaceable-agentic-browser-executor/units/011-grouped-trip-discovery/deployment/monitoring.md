---
version: grouped-6c94033
environment: production
status: verified
---

# Existing monitoring and release follow-up

Use the existing local heartbeat, Docker health, protected application logs, and content-free
coordinator/`price_validation` evidence. This release introduces no external monitoring service,
new alert destination, or asserted availability/latency SLO.

## Post-promotion checks

- Confirm the intended immutable image/revision is running, Docker reports healthy, restart/OOM
  counters are acceptable, and the existing heartbeat advances.
- Check the existing internal/public health endpoints, dependencies, SQLite integrity and foreign
  keys, and the expected published/internal ports. Keep Caddy available through BookSaver changes.
- Review protected logs for startup failures, browser cleanup failures, repeated timeouts, or
  failed caller admission. Keep cookies, identifiers, URLs, account text, keys, and traces local.
- Review code-owned inventory counters and content-free price-validation outcomes: group counts,
  unresolved work, accepted/eligible counts, terminal results, timing, actions and cost. A healthy
  daemon alone does not establish correct reservation discovery or a valid price comparison.

## Response and rollback

Investigate recurrent timeouts, identity mismatches, incomplete coverage, or health degradation
using the existing protected logs and serialized isolated replay procedures. Preserve caller
scope, notification suppression, deadlines, cost limits, and the single browser lease.

The backup under `/opt/booksaver-backups/20260914-grouped-6c94033` is verified: directory
0700, archive 0600, tar verification passed. The retained rollback tag
`booksaver-agent:rollback-pre-grouped-6c94033` is confirmed to point to
`sha256:59740dfc836f97af145503c78f332b09cabaf54ac9fc9c684415d76ec861aa9c`.
If rollback is required, follow existing release procedures and recheck process, health,
heartbeat, logs, dependencies, ports, and state integrity. Do not restore production data merely
because the application image is rolled back.

## Observed post-deployment handoff

Image C started **2026-09-14T20:39:55.097847258Z** at Git merge revision
`933735541e16457ad614daa9c76be24a3af253e4`. Docker is running/healthy, with zero restarts and
OOM false; fresh public/internal health checks returned HTTP 200. Four startup log lines had zero errors/warnings, and no
browser/display processes remained. Only Caddy 80/443 are published; 6080/8080 are internal.
State integrity/foreign-key checks passed. Normal production inventory accepted six discovered
reservations, with two eligible upcoming stays, zero eligible current stays, two verified groups
and zero unresolved items. Staged price evidence remains separate from production inventory;
no native Telegram test is claimed.

Heartbeat advance verified: **1789418425 → 1789418440**. This monitoring handoff is verified
using the existing mechanisms; no new external alerts were introduced.
