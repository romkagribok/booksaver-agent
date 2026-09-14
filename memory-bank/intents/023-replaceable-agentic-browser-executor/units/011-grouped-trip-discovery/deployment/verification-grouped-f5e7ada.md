---
version: grouped-f5e7ada
commit: f5e7ada4d522ad8adf9d0eaaa19858d82371ce15
environment: staging
status: failed
---

# Verification: image B

Immutable artifact: `sha256:f58e058865320c50d9ad289a727d0167c3f369e6f15d6dc2c0a85bea08a04281`.
Image B failed final Staging and is not promotable. Production was not promoted.

## Established evidence

| Check | Observed result |
|---|---|
| Construction quality | 2,609 tests passed; 83% coverage; Ruff and mypy clean |
| AI-DLC checks | 16 validator tests passed; zero artifact errors and status inconsistencies |
| Final-head review | Cursor Bugbot SUCCESS; merge gate passed; two threads resolved |
| Installed artifact | 122 modules, eight pinned versions, CLI and `pip check` passed |
| Native Development smoke | Passed cleanly in 2.68 seconds |
| Grouped inventory | Two groups, both count-verified; zero unresolved; five positives and two eligible |
| Later inventory refresh | Six positives; separate refresh evidence |
| AIRINN price check | Passed in 75.107 seconds; three calls/actions; USD 0.114791; valid refundable match |
| Park Inn final staged check | Failed: timeout at 179.000 seconds; 13 calls, three actions; USD 0.808159; no safety violations |
| Production promotion and verification | Pending |

Image A's Park Inn timeout and the separate 63.278-second diagnostic `no_equivalent_offer` retry
remain in `history.md`. Neither supersedes image B’s failed final staged check.

## Subsequent diagnostics and disposition

The image B solo Park Inn diagnostic succeeded in **87.578 seconds**, with **five model calls**
and **USD 0.188221**. A sequential diagnostic then succeeded for AIRINN in **72.848 seconds**
(**USD 0.112208**) and Park Inn in **130.205 seconds** (**eight calls**, **four actions**,
**USD 0.393550**). These later diagnostic successes do not erase the failed release gate.

Observed Park Inn loops included repeated incomplete submissions without intervening browser
actions. No shared-state leak was confirmed. Candidate C requires its own final-head review and
exact-image staged qualification. No production promotion is claimed.
