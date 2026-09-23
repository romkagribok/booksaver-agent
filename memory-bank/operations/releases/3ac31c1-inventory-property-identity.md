---
version: propertyref-3ac31c1
commit: 3ac31c1a27396a20e606190013da448517a4b43e
created: 2026-09-23T22:27:37Z
status: complete
---

# Inventory property identity — promoted

Owner `/bookings` and `/connect` refreshes rolled back as `persistence_conflict` because the
saved July reservation stored the hotel URL as `/hotel/us/<slug>.html` while the grouped-trip
reader observes `/hotel/us/<slug>.en-us.html`. The conflict was not logged and Telegram advised
retrying. Production data was corrected first, then the rule was fixed so it cannot recur.

## Production data correction (2026-09-23T00:05Z)

Before any code change, a consistent SQLite backup was written to
`/data/booksaver.db.pre-propertyref-20260922` and six legacy locale-free hotel URLs (two rows for
the owner, four for user 4, across `account_reservations` and `bookings`) were rewritten to the
`.en-us.html` form. Every owner refresh since then completed. No active production row has a
missing or non-URL hotel reference.

## Change (PR #69, merged as `4b3d9b9f74a0010b4c3691b5796eb355764695e6`)

- A differing hotel URL no longer conflicts when both references are recognized Booking hotel
  URLs with the same country and slug; host and `.en-us`/`.en-gb` suffix are ignored. The stored
  URL is kept so price validation keeps comparing against the same host.
- A property rename is accepted only under that URL proof and only from the grouped reader, which
  takes name and URL from one verified confirmation-header anchor and marks the observation
  `property_anchor_verified`. Provider-submitted facts never carry the flag.
- Unrecognized URLs, non-English locales, trailing slashes, name-only or legacy non-URL
  references, renames without a URL, and provider renames still fail closed. Booked facts keep
  last-safe authority.
- Persistence conflicts log the disagreeing field names (never values) with run and user id, and
  `persistence_conflict` has its own Telegram guidance.
- Bugbot waiver: Cursor's usage limit blocked Bugbot on every head. The owner waived it and made
  the rule permanent in `AGENTS.md`; `scripts/bugbot_merge_gate.py` now recognizes Cursor's
  current-head usage-limit notice and prints `waived` (nine new gate tests).

## Review and quality

Two independent review passes replaced Bugbot. The first found that the initial commit let
unrecognized or name-only observations replace the hotel identity, that provider output could pair
a matching URL with another hotel's name, and that `secure` versus `www` hosts still conflicted;
commits `534ed01` and `e1d721d` fixed these. The final pass confirmed all findings resolved with no
new bugs. Full suite **3,027 passed**, 1 skipped, 52 existing warnings; Ruff and mypy126 clean;
AI-DLC validator clean.

## Qualified artifact

- Tag `booksaver-agent:propertyref-3ac31c1`, image
  `sha256:d7973b6e0e318dc6e50f4ac23511f4697a9700736d243f76bd74073552e4d07d`, built
  2026-09-23T22:24Z on qualified base `nohelp-9491bcd` (`sha256:8315daba…`).
- Development (`dev-3ac31c1.log`, network disabled): 125 installed modules byte-equal, eight
  dependency pins matched, `pip check` clean, isolated smoke 2.69 s, three supervisor cleanup cases.
- Staging (`stage-3ac31c1.log`): the owner reservation replayed on fresh production snapshots,
  each case on its own copy, no network, no production writes. Accepted: plain refresh, legacy URL,
  host variant, anchored rename (same row; URL, price and room unchanged). Rejected: provider rename
  with matching URL, rename without URL, real room/hotel conflict. Log named fields only.

## Production promotion

`promote-3ac31c1.sh` backed up to `/opt/booksaver-backups/propertyref-3ac31c1-20260923`
(0700/0600, archive SHA-256 `abe98c747d41a36b4545a948d50b0ab9d6a88f5ed23d20cfe65ef8e05cadf5b9`,
verified), passed pre-promotion SQLite integrity and foreign-key checks, fast-forwarded the
production clone to the merge commit, tagged `booksaver-agent:rollback-pre-propertyref-3ac31c1`
(`sha256:8315daba…`), and recreated only BookSaver. Daemon started **2026-09-23T22:27:27Z**;
healthy at **22:27:32Z**; promotion completed 22:27:37Z. Post-promotion: running/healthy,
0 restarts, OOM false, heartbeat 12 s, clean startup log, no host ports, no orphan browser
processes, config unchanged, SQLite quick_check ok at schema 18, public health 200, Caddy
unchanged, disk 25%. Rollback: retag `latest` to the rollback image and recreate; no data restore
implied. Protected evidence: `build-3ac31c1.log`, `dev-3ac31c1.log`, `stage-3ac31c1.log`,
`promotion-3ac31c1.log` in `/opt/booksaver-releases/propertyref-20260923/`.
