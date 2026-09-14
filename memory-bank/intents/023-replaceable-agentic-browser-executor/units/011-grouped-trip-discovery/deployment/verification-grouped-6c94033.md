---
version: grouped-6c94033
commit: 6c9403389c1aa819ef5933cbf820c648e9a12cd7
environment: production
status: passed
---

# Verification: image C

Immutable artifact: `sha256:9ac7a7caa7f204354d5a58a82f6c63bdbfa33a51fc6320fc9a370cbb7cdc3f3a`.

| Check | Observed result |
|---|---|
| Construction quality | 2,623 tests passed; 52 existing warnings; 56.19 seconds; Ruff/mypy clean |
| Coverage | 83%; 20,905 statements, 3,456 missed |
| AI-DLC | 16 validator tests passed; zero errors/inconsistencies; Bolt076 complete |
| Installed artifact | 122 modules, eight pinned versions, CLI and `pip check` passed |
| Native Development | Passed cleanly in 2.78 seconds |
| Final-head Bugbot and merge gate | SUCCESS; gate passed; two resolved review threads |
| Exact-image AIRINN Staging | Success: 75.984 seconds; three calls/actions; USD 0.117024 |
| Exact-image Park Inn Staging, first run | Success: 63.965 seconds; three calls/actions; USD 0.078684 |
| Exact-image Park Inn Staging, repeat | valid_observation / no_equivalent_offer: 64.939 seconds; three calls/actions; USD 0.079272 |
| Production promotion | Qualified image C running; started 2026-09-14T20:39:55.097847258Z; Git 933735541e16457ad614daa9c76be24a3af253e4 |
| Normal production inventory | Accepted; six discovered, two eligible upcoming, zero eligible current, ten saved rows; no failure code; two groups/counts verified, zero unresolved |
| Production process and health | Running/healthy; zero restarts; OOM false; public and internal health HTTP 200, freshly verified |
| Startup and cleanup | Four startup log lines, zero errors/warnings; no browser/display processes |
| State checks | Integrity and foreign-key checks passed |
| Ports | Only Caddy 80/443 published; 6080/8080 internal |
| Backup and rollback | Directory 0700; archive 0600 and tar verified; prior image rollback tag confirmed |
| Heartbeat advance | Verified: 1789418425 → 1789418440 |

A and B failed their release Staging gates. Image B's later successful solo and sequential
diagnostics remain historical evidence in `history.md`; they do not establish image C acceptance.
The validator remains unchanged: price results still require trusted identity, refundability,
equivalence, currency and all-in totals. An incomplete submission or timeout is not a successful
comparison. A validated no-equivalent-offer terminal remains distinct from a found offer.

Staging exited **0**. All three checks reported **zero safety violations** and each produced
one complete submission without a submission loop. The repeat Park Inn result is a validated
observation with no equivalent offer, rather than a found offer; the staged acceptance passed.

PR51 merged at **2026-09-14T20:36:55Z**, merge revision
`933735541e16457ad614daa9c76be24a3af253e4`.

## Production evidence and completion

The exact qualified C image was promoted. Production evidence above is from the normal caller
inventory flow; the three staged price checks used isolated cloned state. No native Telegram
test is claimed. An accepted inventory does not itself establish a fresh production price result.

Protected backup: `/opt/booksaver-backups/20260914-grouped-6c94033`. Confirmed retained rollback
tag: `booksaver-agent:rollback-pre-grouped-6c94033`, pointing to
`sha256:59740dfc836f97af145503c78f332b09cabaf54ac9fc9c684415d76ec861aa9c`.

Final verification passed: heartbeat advanced **1789418425 → 1789418440** and fresh public/internal
health checks returned HTTP **200**. Monitoring uses existing mechanisms, with no new external
alerts. Preserve account text, identifiers, credential-bearing URLs and protected logs locally.
