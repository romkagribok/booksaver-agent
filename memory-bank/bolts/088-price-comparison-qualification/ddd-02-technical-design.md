---
stage: technical-design
bolt: 088-price-comparison-qualification
created: "2026-10-10T01:49:00Z"
status: complete
---

# Release qualification and activation — technical design

Qualification reuses the established release kit on the VPS (`/opt/booksaver-releases/<name>/`):
build on the last qualified image, verify installed source against the tree, `pip check`, daemon
and Chromium smoke, supervisor cleanup cases, then a release-specific stage probe against a
`sqlite3.backup` copy of production with `--network none`. Promotion backs up config, environment
and data with checksums, fast-forwards the checkout to the reviewed merge, retags `latest`,
recreates only the BookSaver container, verifies health, heartbeat, ports, SQLite integrity and
schema, and restores the previous image and config automatically on failure.

No new mechanism is built by this bolt; it records the evidence and the kill-switch exercise.
