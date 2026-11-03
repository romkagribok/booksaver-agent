---
stage: plan
bolt: 096-codex-merge-gate
created: 2026-11-03T01:23:31Z
---

# Implementation Plan: Codex merge gate

Bugbot reported on PR #90 that it is disabled for the owner's account. The owner chose on 2026-11-03
to make Codex the required review. The Codex GitHub connector records its result in a
`codex-review-state:v1` comment with the reviewed commit, status and unresolved-findings flag, so the
gate reads that rather than inferring from comments. Replace the script and its test, and update
`AGENTS.md` and the pull-request template.
