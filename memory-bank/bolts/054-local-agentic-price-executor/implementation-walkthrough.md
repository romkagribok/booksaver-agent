---
stage: implement
bolt: 054-local-agentic-price-executor
created: 2026-08-25T01:15:00Z
status: complete
---

# Implementation Walkthrough: Container-Compatible Stagehand Launch

## Summary

The local Stagehand adapter now specifies the production container's Chromium compatibility mode
directly. The image continues to run BookSaver and Chromium as the unprivileged `booksaver` user,
and all trusted control-plane boundaries are unchanged.

## Structure Overview

The correction stays at the infrastructure browser-launch seam. Unit coverage replaces the external
launchers with local fakes, while deployment coverage keeps the image's unprivileged runtime and
absence of a CI workaround explicit.

## Completed Work

- [x] `src/booksaver/infrastructure/browser/agentic_executor.py` - Declares the Stagehand Chromium
  launch compatibility setting.
- [x] `tests/unit/test_agentic_browser_executor.py` - Proves the exact launch request and teardown.
- [x] `tests/unit/test_remote_auth_deployment.py` - Preserves the non-root image and rejects a CI
  environment workaround.
- [x] `Dockerfile` - Accurately documents the image's runtime security boundary.

## Key Decisions

- **Explicit adapter policy**: Production launch behavior must not depend on Stagehand inferring a
  browser flag from the generic `CI` environment variable.
- **No operator toggle**: The setting is part of the supported Docker runtime contract, not a new
  configurable security mode.

## Deviations from Plan

None.

## Dependencies Added

None.

## Developer Notes

The exact built image still requires a Stagehand launch/attach/teardown smoke before promotion.
