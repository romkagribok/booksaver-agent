---
version: reconciliation-153d432
commit: 153d4320dd553e2d2c58d5231949697991009212
built: 2026-09-20T18:05:08.641935651Z
created: 2026-09-20T18:11:30Z
status: success
---

# Build: reviewed trusted inventory reconciliation

- Tag: `booksaver-agent:reconciliation-153d432`.
- Immutable image: `sha256:cddc642f8a3e6b1babaa070000c530027362de2933ab47575008fc7d5141155b`.
- Size: **701,874,085 bytes**.
- Source: `153d4320dd553e2d2c58d5231949697991009212`.
- Qualified base: `sha256:9ac7a7caa7f204354d5a58a82f6c63bdbfa33a51fc6320fc9a370cbb7cdc3f3a`; dependencies unchanged.

All **123 installed modules** match source; **eight dependency pins**, `pip check` and CLI passed.
Network-disabled isolated Development passed SQLite/FKs, Chromium and clean shutdown in **2.72 seconds**.
Exact installed-image Staging passed **39 checks**, zero failures: COMPLETE inventory, four discovered,
two eligible; old reservation absent/archived and separate replacement active/eligible. All 658
other-caller rows were unchanged; integrity/FKs and read-only source digest protection passed.

Post-review quality: **2,818 tests**, **52 existing warnings**, **52.42 seconds**; Ruff/mypy123 clean.
Current-head Cursor Bugbot **SUCCESS** in **3m29s**; the merge gate passed with **two resolved
threads**, zero unresolved. This image supersedes fe8ba21, which passed earlier Dev/Staging but
was not promoted; its historical record is preserved.

PR53 merged at **2026-09-20T18:12:16Z**, revision `ef51bc8a5b4367d55e59af4644d1d3178db7d957`; its full tree matches reviewed 153d432.
This exact image was promoted, daemon started **2026-09-20T18:14:31.784745376Z**, and independent
production verification passed at **2026-09-20T18:15:28Z**. See history/verification for reconciliation,
health, backup and rollback evidence. Native Telegram UI remains user-driven.
