---
version: grouped-6c94033
environment: production
status: success
---

# Release history

The user's standing authorization covers construction, review, build, Development/Staging,
merge, and production promotion. Bolt074, Bolt075, and Bolt076 are construction-complete.
Production promotion, normal caller inventory, and final health/heartbeat verification succeeded.

## Initial image A — staging failed; not promotable

Source: `4a8582a502dc5d3d5ee9ec332aec5ef4791b3d87`. Immutable image:
`sha256:c97023742f8c44ac469fb68caed0dfa66b9528fb5cdbcd4b4956c86dab4e3793`.

Development checks passed, including the clean **2.87-second** isolated native smoke. Staging used
installed image source, cloned production state, read-only access to the original volume,
notifications disabled, and serialized normal caller flow under a daemon restart trap.

- AIRINN authenticated price check succeeded in **64.090 seconds**.
- Park Inn timed out at approximately **179 seconds**, after **12 model calls**, **4 actions**,
  and **USD 0.584237**, with no reported safety violations.

Image A failed staging and must not be promoted. Its passing first check remains historical
evidence only; review corrections required replacement image B.

## Separate Park Inn diagnostic retry

A diagnostic retry completed in **63.278 seconds** with a validated page and
`no_equivalent_offer`, rather than a timeout. This is diagnostic evidence, not proof that image
B's final staged Park Inn check passed. No image identity or additional result is inferred here.

## Image B — Staging failed; not promotable

Built **2026-09-14T19:43:21Z** from source
`f5e7ada4d522ad8adf9d0eaaa19858d82371ce15`. Immutable image:
`sha256:f58e058865320c50d9ad289a727d0167c3f369e6f15d6dc2c0a85bea08a04281`.

- Installed-source checks covered **122 modules**, **eight pinned versions**, CLI and `pip check`.
  The native Development smoke passed cleanly in **2.68 seconds**.
- The final-head Cursor Bugbot check is **SUCCESS**; the merge gate passed with **two resolved
  review threads**.
- Inventory recorded **2 groups**, **2 verified group counts**, **0 unresolved items**, **5 positive
  reservations**, and **2 eligible stays**. A later refresh recorded **6 positives**. These are
  separate observed refresh results; neither grants absence authority.
- AIRINN's staged authenticated price check passed in **75.107 seconds**, with **3 model calls**,
  **3 actions**, **USD 0.114791**, and a valid refundable match.
- Park Inn's final staged check **failed** with a **179.000-second timeout**, **13 model calls**,
  **3 actions**, **USD 0.808159**, and no safety violations. Image B is not promotable.

### Image B subsequent diagnostics

A solo Park Inn diagnostic succeeded in **87.578 seconds**, with **5 calls** and **USD 0.188221**.
A sequential diagnostic succeeded for AIRINN in **72.848 seconds** (**USD 0.112208**) and Park Inn
in **130.205 seconds** (**8 calls**, **4 actions**, **USD 0.393550**). These successes do not
replace the failed release Staging gate.

The observed Park Inn loop contained repeated incomplete submissions without intervening browser
actions. No shared-state leak was confirmed.

## Image C — Development, review and Staging passed

Built **2026-09-14T20:23:33.817225283Z** from source
`6c9403389c1aa819ef5933cbf820c648e9a12cd7`. Immutable image:
`sha256:9ac7a7caa7f204354d5a58a82f6c63bdbfa33a51fc6320fc9a370cbb7cdc3f3a`.

- Uses the same qualified base and recipe as A/B; size **699,629,490 bytes**.
- Archive SHA256: `1a95ca8eb963bba3f675fb4a8ab220ead039490dc10f53a3f673d8914d5b5db4`.
- Installed checks passed for **122 modules**, **eight pinned versions**, CLI and `pip check`;
  native Development passed cleanly in **2.78 seconds**.
- Bolt076 source quality: **2,623 tests**, **52 existing warnings**, **56.19 seconds**; **83%**
  coverage (20,905 statements, 3,456 missed); Ruff/mypy clean; 16 validator tests passed;
  zero artifact errors/status inconsistencies.
- Clarifies query versus per-offer completeness, advertises existing closed statuses, and captures
  `finally` diagnostics; the acceptance validator remains unchanged.
- Final-head Cursor Bugbot is **SUCCESS**; the merge gate passed with **two resolved threads**.
- Exact-image Staging exited **0**: AIRINN succeeded in **75.984 seconds**, **3 calls**, **3 actions**,
  **USD 0.117024**; Park Inn first run succeeded in **63.965 seconds**, **3 calls**, **3 actions**,
  **USD 0.078684**; Park Inn repeat returned `valid_observation` / `no_equivalent_offer` in
  **64.939 seconds**, **3 calls**, **3 actions**, **USD 0.079272**.
- All three checks had **zero safety violations**, each with one complete submission and no loop.
  The repeat result is a validated no-equivalent-offer outcome, not a claimed found offer.
- PR51 merged at **2026-09-14T20:36:55Z**, merge revision
  `933735541e16457ad614daa9c76be24a3af253e4`.

## Production — promoted and verified

The qualified image C was promoted and the runtime started at
**2026-09-14T20:39:55.097847258Z**. The checkout is merge revision
`933735541e16457ad614daa9c76be24a3af253e4`; the running image is
`sha256:9ac7a7caa7f204354d5a58a82f6c63bdbfa33a51fc6320fc9a370cbb7cdc3f3a`.

The normal production caller inventory was accepted, with **6 discovered reservations**,
**2 eligible upcoming stays**, **0 eligible current stays**, **10 saved rows**, and no failure
code. Coverage recorded **2 groups**, **2 verified counts**, and **0 unresolved items**.
Integrity and foreign-key checks passed. These are production inventory results; the price
checks above ran in isolated cloned state. No native Telegram interaction is claimed.

Docker is running and healthy with **0 restarts**, **OOM false**, and freshly verified public/internal health HTTP **200**.
Startup logs contained **4 lines**, **0 errors**, and **0 warnings**. No browser/display
processes remained. Only Caddy ports **80/443** are published; **6080/8080** remain internal.
The heartbeat advanced from **1789418425** to **1789418440**.

Backup `/opt/booksaver-backups/20260914-grouped-6c94033` has mode **0700**, its archive has
mode **0600**, and tar verification passed. The retained tag
`booksaver-agent:rollback-pre-grouped-6c94033` was confirmed to point to the previous image
`sha256:59740dfc836f97af145503c78f332b09cabaf54ac9fc9c684415d76ec861aa9c`.

Release verification is complete using the existing monitoring mechanisms.
