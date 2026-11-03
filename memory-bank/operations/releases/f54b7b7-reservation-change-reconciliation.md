---
version: reschange-f54b7b7
commit: f54b7b7d11a9
created: "2026-11-03T01:22:09Z"
status: deployed-verified
recorded: "2026-11-03T03:45:20Z"
---

# Changed reservations are followed, and Jev stays in the booked currency (intent 028, release 1)

The owner moved a reservation to new dates under the same confirmation number. From 2026-10-26
every sync failed with `persistence_conflict` and the booking received no price check; the six
checks before that failed with `currency_mismatch`. Nobody was told.

## Change

- Bolt 093 (ADR-059): code-read stay, room, occupancy and refund facts replace saved ones for the
  same confirmation and a proven hotel. Facts not re-read after a change are cleared and the
  reservation is held without a verified total. Provider output cannot release a hold.
- Bolt 094: Jev re-opens the redirected property page once with `selected_currency`.

## Artifact and verification

- PR #90, head `f54b7b7`; merge `fe1b457080e7080c26773a39847d00d570a62a30`, `src` identical.
- Image `booksaver-agent:reschange-f54b7b7` =
  `sha256:6c8455d1fc4a9a018365f9c7dc0b5f3e92cd0544c57459487082fa29243d2c0a`, built on
  `jevonly-a273c78`.
- Quality: 3,325 passed, 1 skipped; Ruff and mypy clean; AI-DLC validators 0 errors.
- Review: Codex found three issues on the first head (unread room kept, provider total could
  release a hold, hotel not proven), all fixed with tests; clean on `f54b7b7`. **Bugbot did not
  run**: Cursor reported it is disabled for the owner's account. The owner chose "Codex replaces
  Bugbot" (2026-11-03); the gate changed in PR #91.
- Dev on the exact image: 133 modules match, pins matched, schema, foreign keys, Chromium, clean stop.
- Live replay on the exact image (kit `reschange-20261103`, daemon paused, cloned database, owner's
  real page): sync complete, stay moved to 2027-04-15/16, baseline USD 346.08 to 659.68, same booking,
  22 old opportunities removed; one Jev check pinned the currency, 8 offers accepted, success at
  USD 581, one opportunity created.
- Promotion: backup `/opt/booksaver-backups/reschange-f54b7b7-20261103`, healthy, schema 21, public
  health passed, Caddy unchanged, at 2026-11-03T01:22:09Z. Rollback tag
  `booksaver-agent:rollback-pre-reschange-f54b7b7`.

## Production read-back

- 2026-11-03T05:39Z and 13:39Z: the owner's scheduled syncs completed with no conflict; reservation and
  booking on 2027-04-15/16 at USD 659.68. Both price checks after them succeeded at USD 592 (the
  currency pin worked on the live daemon).
- 2026-11-03T13:40Z: savings alert delivered for USD 592 against USD 659.68 (USD 67.68). The owner
  confirmed receiving it in Telegram.
- No stall notice was sent (none due); `monitoring_stall_notices` empty. The stall path itself has
  not yet fired in production.
