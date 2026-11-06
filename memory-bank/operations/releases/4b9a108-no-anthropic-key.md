---
version: releasea-4b9a108
commit: 4b9a108
created: "2026-11-06T01:22:32Z"
status: deployed-verified
recorded: "2026-11-06T01:23:40Z"
---

# Every user on Jev, no Anthropic key (intent 030 release A)

## Change

Bolt 099 (ADR-062): routing no longer depends on disclosure acceptance in any mode; invitees are
informed once that TypeSafe's Jev reads page content (only when Jev is the price method); the
`/connect` disclosure names TypeSafe; account sync never starts the Claude navigation agent (removed
from discovery); inventory executors need no key.

## Artifact and verification

- PR #100, head `4b9a108`, merge `28a9a8f59482`, `src` identical.
- Image `booksaver-agent:releasea-4b9a108` =
  `sha256:04b382d81def6ddfcc455c47c4ddfa405fe27cbc61a17ff3677e72be9b0c6536`, built on
  `tripcount-b40e9b4`.
- Quality: 3,262 passed, 1 skipped; Ruff and mypy clean; AI-DLC validators 0 errors.
- Review: Codex, four rounds; three findings fixed (fallback even with a key, disclosure tied to the
  Jev executor, agentic-mode gate); clean on `4b9a108`.
- Live replay on the exact image with `BOOKSAVER_LLM_API_KEY` empty: owner, dad and third invitee
  syncs complete; owner's Jev check success at USD 581; 0 Anthropic calls.
- Promotion: backup `/opt/booksaver-backups/releasea-4b9a108-20261106`, healthy, schema 23, public
  health passed, at 2026-11-06T01:22:32Z.
- Config: `disclosure_version` set to `typesafe-visible-booking-page-v1`; `BOOKSAVER_LLM_API_KEY`
  removed from `/opt/booksaver-agent/.env`; container recreated healthy with the key empty
  (originals in the backup). The owner is asked to revoke the key at Anthropic.

## Production read-back

- 2026-11-06T07:15Z to 10:57Z: five scheduled syncs (owner 2, dad 1, third invitee 2) complete; owner's
  Jev checks succeeded at USD 581 (twice), the dad's new Best Western at USD 504; 0 Anthropic calls.
- Inform-once: both invitees' records moved to `typesafe-visible-booking-page-v1` (07:15Z, 10:57Z),
  so each received the TypeSafe message once.
