---
stage: implement
bolt: 096-codex-merge-gate
created: 2026-11-03T01:23:31Z
---

# Implementation Walkthrough: Codex merge gate

- `scripts/codex_merge_gate.py` replaces `scripts/bugbot_merge_gate.py`, with a smaller pure
  `evaluate_gate` and one `gh` call per fact. It only trusts comments by the Codex connector.
- The usage-limit wording is not observed yet. The gate matches "usage limit" in a Codex comment
  that is not the state comment and is newer than the head commit. Correct it if the real notice
  differs. The miss direction is blocked, not passed.
- Historical records that mention Bugbot are unchanged.
