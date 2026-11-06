---
unit: 003-delete-claude-code
bolt: 100-delete-claude-code
stage: test
status: complete
created: 2026-11-06T03:03:29Z
updated: 2026-11-06T03:03:29Z
---

# Test Report - Delete the Claude Code

## Step 1 (PR #102, merged)

3,109 passed, 1 skipped; live replay with no Anthropic key identical to release A.

## Step 2 (with bolt 101)

- Full suite 2,600 passed, 1 skipped (tests of deleted code removed); Ruff clean; mypy clean for 116
  modules; no source file imports `anthropic` or `stagehand` or reads `BOOKSAVER_LLM_API_KEY`.
- Source: about 53,600 lines before the cleanup, 32,936 after (step 1 about -11,000, step 2 about
  -26,000 including tests).
- Image: the release Dockerfile layered new source over the old tree, so deleted modules survived in
  `/app/src`, `/app/build` and site-packages. The kit Dockerfile now clears all three and uninstalls
  the old package and `stagehand`; the candidate holds 116 modules and only `typesafe_client.py` in
  `llm/`.
- Live replay on the clean image (kit `releaseb2-20261106`, cloned data, no key): owner, dad and the
  third invitee sync complete with unchanged facts; owner's Jev check success at USD 581; migration
  to schema 24 dropped the three Claude tables; no personal keys stored; the production config loads
  with one retired-key warning.
- Production qualification state checked read-only: none stored, so collapsing routing changes no
  user's path.
