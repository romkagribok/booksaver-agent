---
version: grouped-4a8582a
environment: staging
status: failed
---

# Release history

User authorization covers construction, review, build, Dev/Staging, merge and production promotion.
Construction was completed by the official cascade script after actual caller 22 success and the
2,564-test/83%-coverage gate. Production remains PR50 while this release is qualified.

## Development — passed

Installed source/dependencies/CLI checks passed. With only BookSaver paused and Caddy retained,
an isolated no-network Chromium/native daemon smoke passed and shut down cleanly in 2.87 seconds.

## Initial image A staging — failed; not promotable

Exact image `sha256:c97023742f8c44ac469fb68caed0dfa66b9528fb5cdbcd4b4956c86dab4e3793`
ran normal invited-caller inventory and immediate checks for both
eligible stays on cloned production state. Original volume is read-only, notifications are off,
and imports resolve to `/usr/local/lib/python3.12/site-packages/booksaver`; PYTHONPATH includes
operator helpers only. No application source overlay is active. A restart trap restores the old
daemon after staging.

- AIRINN authenticated price check: succeeded in **64.090 seconds**.
- Park Inn authenticated price check: **timeout at approximately 179 seconds**, **12 model calls**,
  **4 actions**, **USD 0.584237**, and **no reported safety violations**.

The initial image therefore failed staging and must not be promoted. Bolt075's current review
fixes also require a replacement image built from the final reviewed source. Replacement-image
Dev/Staging verification, final-head Bugbot, merge, and production promotion remain pending.
The first check's success is retained as historical evidence only; no promotion is recorded.
